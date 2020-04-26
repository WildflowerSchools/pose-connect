import process_pose_data.fetch
import cv_utils
import cv2 as cv
import pandas as pd
import numpy as np
import tqdm
import logging
import time
import itertools

logger = logging.getLogger(__name__)

def filter_keypoints_by_quality(
    df,
    min_keypoint_quality=None,
    max_keypoint_quality=None,
    inplace=False
):
    # Make copy of input dataframe if operation is not in place
    if inplace:
        df_filtered = df
    else:
        df_filtered = df.copy()
    keypoint_coordinate_arrays = df_filtered['keypoint_coordinates'].values
    num_keypoint_coordinate_arrays = len(keypoint_coordinate_arrays)
    keypoint_coordinates = np.concatenate(keypoint_coordinate_arrays, axis = 0)
    keypoint_quality_arrays = df_filtered['keypoint_quality'].values
    num_keypoint_quality_arrays = len(keypoint_quality_arrays)
    keypoint_quality = np.concatenate(keypoint_quality_arrays)
    if num_keypoint_coordinate_arrays != num_keypoint_quality_arrays:
        raise ValueError('Number of keypoint coordinate arrays ({}) does not match number of keypoint quality arrays ({})'.format(
            num_keypoint_coordinate_arrays,
            num_keypoint_quality_arrays
        ))
    num_spatial_dimensions_per_keypoint = keypoint_coordinates.shape[1]
    if min_keypoint_quality is not None:
        mask = np.less(
            keypoint_quality,
            min_keypoint_quality,
            where=~np.isnan(keypoint_quality)
        )
        keypoint_coordinates[mask] = np.array(num_spatial_dimensions_per_keypoint*[np.nan])
        keypoint_quality[mask] = np.nan
    if max_keypoint_quality is not None:
        mask = np.greater(
            keypoint_quality,
            max_keypoint_quality,
            where=~np.isnan(keypoint_quality)
        )
        keypoint_coordinates[mask] = np.array(num_spatial_dimensions_per_keypoint*[np.nan])
        keypoint_quality[mask] = np.nan
    df_filtered['keypoint_coordinates'] = np.split(keypoint_coordinates, num_keypoint_coordinate_arrays)
    df_filtered['keypoint_quality'] = np.split(keypoint_quality, num_keypoint_quality_arrays)
    if not inplace:
        return df_filtered

def filter_poses_by_num_valid_keypoints(
    df,
    min_num_keypoints=None,
    max_num_keypoints=None,
    inplace=False
):
    # Make copy of input dataframe if operation is not in place
    if inplace:
        df_filtered = df
    else:
        df_filtered = df.copy()
    num_keypoints = df['keypoint_quality'].apply(
        lambda x: np.count_nonzero(~np.isnan(x))
    )
    if min_num_keypoints is not None:
        df_filtered = df_filtered.loc[num_keypoints >= min_num_keypoints]
    if max_num_keypoints is not None:
        df_filtered = df_filtered.loc[num_keypoints <= max_num_keypoints]
    if not inplace:
        return df_filtered

def filter_poses_by_quality(
    df,
    min_pose_quality=None,
    max_pose_quality=None,
    inplace=False
):
    # Make copy of input dataframe if operation is not in place
    if inplace:
        df_filtered = df
    else:
        df_filtered = df.copy()
    if min_pose_quality is not None:
        df_filtered = df_filtered.loc[df_filtered['pose_quality'] >= min_pose_quality]
    if max_pose_quality is not None:
        df_filtered = df_filtered.loc[df_filtered['pose_quality'] <= max_pose_quality]
    if not inplace:
        return df_filtered

def filter_pose_pairs_by_score(
    df,
    min_score=None,
    max_score=None,
    inplace=False
):
    # Make copy of input dataframe if operation is not in place
    if inplace:
        df_filtered = df
    else:
        df_filtered = df.copy()
    if min_score is not None:
        df_filtered = df_filtered.loc[df_filtered['score'] >= min_score]
    if max_score is not None:
        df_filtered = df_filtered.loc[df_filtered['score'] <= max_score]
    if not inplace:
        return df_filtered

# TODO: Replace this function with one that uses the other functions below
def process_poses_by_timestamp(
    df,
    distance_method='pixels',
    summary_method='rms',
    pixel_distance_scale=5.0,
    progress_bar=False,
    notebook=False
):
    num_poses = len(df)
    num_timestamps = len(df['timestamp'].unique())
    start = df['timestamp'].min().to_pydatetime()
    end = df['timestamp'].max().to_pydatetime()
    time_span = end - start
    time_span_seconds = time_span.total_seconds()
    camera_ids = df['camera_id'].unique().tolist()
    num_cameras = len(camera_ids)
    logger.info('Fetching camera calibration data for {} cameras'.format(
        num_cameras
    ))
    camera_calibrations = process_pose_data.fetch.fetch_camera_calibrations(
        camera_ids=camera_ids,
        start=start,
        end=end
    )
    logger.info('Processing {} 2D poses spanning {} cameras and {:.1f} seconds ({} time steps)'.format(
        num_poses,
        num_cameras,
        time_span_seconds,
        num_timestamps
    ))
    overall_start_time = time.time()
    df_timestamp_list = list()
    timestamp_iterator = df.groupby('timestamp')
    if progress_bar:
        if notebook:
            timestamp_iterator = tqdm.tqdm_notebook(timestamp_iterator)
        else:
            timestamp_iterator = tqdm.tqdm(timestamp_iterator)
    for timestamp, df_timestamp in timestamp_iterator:
        df_timestamp = generate_pose_pairs_timestamp(
            df=df_timestamp
        )
        df_timestamp = calculate_3d_poses(
            df=df_timestamp,
            camera_calibrations=camera_calibrations
        )
        df_timestamp = score_pose_pairs(
            df_timestamp,
            distance_method=distance_method,
            summary_method=summary_method,
            pixel_distance_scale=pixel_distance_scale
        )
        df_timestamp.insert(
            loc=0,
            column='timestamp',
            value=timestamp
        )
        df_timestamp_list.append(df_timestamp)
    df_processed = pd.concat(df_timestamp_list)
    overall_elapsed_time = time.time() - overall_start_time
    logger.info('Processed {} 2D poses spanning {:.1f} seconds in {:.1f} seconds (ratio of {:.3f})'.format(
        num_poses,
        time_span_seconds,
        overall_elapsed_time,
        overall_elapsed_time/time_span_seconds
    ))
    return df_processed

def generate_pose_pairs(
    df
):
    pose_pairs = df.groupby('timestamp').apply(generate_pose_pairs_timestamp)
    pose_pairs.reset_index(
        level='timestamp',
        inplace=True
    )
    return pose_pairs

def generate_pose_pairs_timestamp(
    df
):
    timestamps = df['timestamp'].unique()
    if len(timestamps) > 1:
        raise ValueError('More than one timestamp in data frame')
    camera_ids = df['camera_id'].unique().tolist()
    pose_id_pairs = list()
    for camera_id_a, camera_id_b in itertools.combinations(camera_ids, 2):
        pose_ids_a = df.loc[df['camera_id'] == camera_id_a].index.tolist()
        pose_ids_b = df.loc[df['camera_id'] == camera_id_b].index.tolist()
        pose_id_pairs_camera_pair = list(itertools.product(pose_ids_a, pose_ids_b))
        pose_id_pairs.extend(pose_id_pairs_camera_pair)
    pose_ids_a = list()
    pose_ids_b = list()
    if len(pose_id_pairs) > 0:
        pose_ids_a, pose_ids_b = map(list, zip(*pose_id_pairs))
    pose_pairs_timestamp = pd.concat(
        (df.loc[pose_ids_a].reset_index(), df.loc[pose_ids_b].reset_index()),
        keys=['a', 'b'],
        axis=1
    )
    pose_pairs_timestamp.set_index(
        [('a', 'pose_id'), ('b', 'pose_id')],
        inplace=True
    )
    pose_pairs_timestamp.rename_axis(
        ['pose_id_a', 'pose_id_b'],
        inplace=True
    )
    pose_pairs_timestamp.columns = ['{}_{}'.format(column_name[1], column_name[0]) for column_name in pose_pairs_timestamp.columns.values]
    pose_pairs_timestamp.drop(
        columns=['timestamp_a', 'timestamp_b'],
        inplace=True
    )
    return pose_pairs_timestamp

def calculate_3d_poses(
    df,
    camera_calibrations=None
):
    if camera_calibrations is None:
        camera_ids = np.union1d(
            df['camera_id_a'].unique(),
            df['camera_id_b'].unique()
        ).tolist()
        start = df['timestamp'].min().to_pydatetime()
        end = df['timestamp'].max().to_pydatetime()
        camera_calibrations = process_pose_data.fetch.fetch_camera_calibrations(
            camera_ids=camera_ids,
            start=start,
            end=end
        )
    df = df.groupby(['camera_id_a', 'camera_id_b']).apply(
        lambda x: calculate_3d_poses_camera_pair(x, camera_calibrations)
    )
    return df

def calculate_3d_poses_camera_pair(
    df,
    camera_calibrations
):
    num_pose_pairs = len(df)
    camera_ids_a = df['camera_id_a'].unique()
    camera_ids_b = df['camera_id_b'].unique()
    if len(camera_ids_a) > 1:
        raise ValueError('More than one camera ID found for camera A')
    if len(camera_ids_b) > 1:
        raise ValueError('More than one camera ID found for camera B')
    camera_id_a = camera_ids_a[0]
    camera_id_b = camera_ids_b[0]
    if camera_id_a not in camera_calibrations.keys():
        raise ValueError('Camera ID {} not found in camera calibration data'.format(
            camera_id_a
        ))
    if camera_id_b not in camera_calibrations.keys():
        raise ValueError('Camera ID {} not found in camera calibration data'.format(
            camera_id_b
        ))
    camera_calibration_a = camera_calibrations[camera_id_a]
    camera_calibration_b = camera_calibrations[camera_id_b]
    keypoint_a_lengths = df['keypoint_coordinates_a'].apply(lambda x: x.shape[0]).unique()
    keypoint_b_lengths = df['keypoint_coordinates_b'].apply(lambda x: x.shape[0]).unique()
    if len(keypoint_a_lengths) > 1:
        raise ValueError('Keypoint arrays in column A have differing numbers of keypoints')
    if len(keypoint_b_lengths) > 1:
        raise ValueError('Keypoint arrays in column B have differing numbers of keypoints')
    if keypoint_a_lengths[0] != keypoint_b_lengths[0]:
        raise ValueError('Keypoint arrays in column A have different number of keypoints than keypoint arrays in column B')
    keypoints_a = np.concatenate(df['keypoint_coordinates_a'].values)
    keypoints_b = np.concatenate(df['keypoint_coordinates_b'].values)
    keypoints_3d = triangulate_image_points(
        image_points_1=keypoints_a,
        image_points_2=keypoints_b,
        camera_matrix_1=camera_calibration_a['camera_matrix'],
        distortion_coefficients_1=camera_calibration_a['distortion_coefficients'],
        rotation_vector_1=camera_calibration_a['rotation_vector'],
        translation_vector_1=camera_calibration_a['translation_vector'],
        camera_matrix_2=camera_calibration_b['camera_matrix'],
        distortion_coefficients_2=camera_calibration_b['distortion_coefficients'],
        rotation_vector_2=camera_calibration_b['rotation_vector'],
        translation_vector_2=camera_calibration_b['translation_vector']
    )
    keypoints_a_reprojected = cv_utils.project_points(
        object_points=keypoints_3d,
        rotation_vector=camera_calibration_a['rotation_vector'],
        translation_vector=camera_calibration_a['translation_vector'],
        camera_matrix=camera_calibration_a['camera_matrix'],
        distortion_coefficients=camera_calibration_a['distortion_coefficients']
    )
    keypoints_b_reprojected = cv_utils.project_points(
        object_points=keypoints_3d,
        rotation_vector=camera_calibration_b['rotation_vector'],
        translation_vector=camera_calibration_b['translation_vector'],
        camera_matrix=camera_calibration_b['camera_matrix'],
        distortion_coefficients=camera_calibration_b['distortion_coefficients']
    )
    df['keypoint_coordinates_3d'] = np.split(keypoints_3d, num_pose_pairs)
    df['keypoint_coordinates_a_reprojected'] = np.split(keypoints_a_reprojected, num_pose_pairs)
    df['keypoint_coordinates_b_reprojected'] = np.split(keypoints_b_reprojected, num_pose_pairs)
    return df

def triangulate_image_points(
    image_points_1,
    image_points_2,
    camera_matrix_1,
    distortion_coefficients_1,
    rotation_vector_1,
    translation_vector_1,
    camera_matrix_2,
    distortion_coefficients_2,
    rotation_vector_2,
    translation_vector_2
):
    image_points_1 = np.asarray(image_points_1)
    image_points_2 = np.asarray(image_points_2)
    camera_matrix_1 = np.asarray(camera_matrix_1)
    distortion_coefficients_1 = np.asarray(distortion_coefficients_1)
    rotation_vector_1 = np.asarray(rotation_vector_1)
    translation_vector_1 = np.asarray(translation_vector_1)
    camera_matrix_2 = np.asarray(camera_matrix_2)
    distortion_coefficients_2 = np.asarray(distortion_coefficients_2)
    rotation_vector_2 = np.asarray(rotation_vector_2)
    translation_vector_2 = np.asarray(translation_vector_2)
    if image_points_1.size == 0 or image_points_2.size == 0:
        return np.zeros((0, 3))
    if image_points_1.shape != image_points_2.shape:
        raise ValueError('Sets of image points do not appear to be the same shape')
    image_points_shape = image_points_1.shape
    image_points_1 = image_points_1.reshape((-1, 2))
    image_points_2 = image_points_2.reshape((-1, 2))
    camera_matrix_1 = camera_matrix_1.reshape((3, 3))
    distortion_coefficients_1 = np.squeeze(distortion_coefficients_1)
    rotation_vector_1 = rotation_vector_1.reshape(3)
    translation_vector_1 = translation_vector_1.reshape(3)
    camera_matrix_2 = camera_matrix_2.reshape((3, 3))
    distortion_coefficients_2 = np.squeeze(distortion_coefficients_2)
    rotation_vector_2 = rotation_vector_2.reshape(3)
    translation_vector_2 = translation_vector_2.reshape(3)
    image_points_1_undistorted = cv_utils.undistort_points(
        image_points_1,
        camera_matrix_1,
        distortion_coefficients_1
    )
    image_points_2_undistorted = cv_utils.undistort_points(
        image_points_2,
        camera_matrix_2,
        distortion_coefficients_2
    )
    projection_matrix_1 = cv_utils.generate_projection_matrix(
        camera_matrix_1,
        rotation_vector_1,
        translation_vector_1)
    projection_matrix_2 = cv_utils.generate_projection_matrix(
        camera_matrix_2,
        rotation_vector_2,
        translation_vector_2)
    object_points_homogeneous = cv.triangulatePoints(
        projection_matrix_1,
        projection_matrix_2,
        image_points_1.T,
        image_points_2.T)
    object_points = cv.convertPointsFromHomogeneous(
        object_points_homogeneous.T
    )
    object_points = np.squeeze(object_points)
    object_points.reshape(image_points_shape[:-1] + (3,))
    return object_points

def score_pose_pairs(
    df,
    distance_method='pixels',
    summary_method='rms',
    pixel_distance_scale=5.0
):
    reprojection_difference = np.stack(
        (
            np.subtract(
                np.stack(df['keypoint_coordinates_a_reprojected']),
                np.stack(df['keypoint_coordinates_a'])
            ),
            np.subtract(
                np.stack(df['keypoint_coordinates_b_reprojected']),
                np.stack(df['keypoint_coordinates_b'])
            )
        ),
        axis=-2
    )
    if distance_method == 'pixels':
        distance = pixel_distance(reprojection_difference)
    elif distance_method == 'probability':
        distance = probability_distance(
            reprojection_difference,
            pixel_distance_scale=pixel_distance_scale
        )
    else:
        raise ValueError('Distance method not recognized')
    if summary_method == 'rms':
        score = np.sqrt(np.nanmean(np.square(distance), axis=(-1, -2)))
    elif summary_method == 'sum':
        score = np.nansum(distance, axis=(-1, -2))
    else:
        raise ValueError('Summary method not recognized')
    df_copy = df.copy()
    df_copy['score'] = score
    return df_copy

def pixel_distance(image_point_differences):
    return np.linalg.norm(image_point_differences, axis=-1)

def probability_distance(image_point_differences, pixel_distance_scale):
    return np.multiply(
        1/np.sqrt(2*np.pi*pixel_distance_scale**2),
        np.exp(
            np.divide(
                -np.square(pixel_distance(image_point_differences)),
                2*pixel_distance_scale**2
            )
        )
    )

def identify_matches(
    df
):
    df_copy = df.copy()
    match_indices = extract_match_indices(df)
    df_copy['match'] = False
    df_copy.loc[match_indices, 'match'] = True
    return df_copy

def extract_match_indices(
    df
):
    best_a_match_for_b = df['score'].groupby('pose_id_b').idxmin()
    best_b_match_for_a = df['score'].groupby('pose_id_a').idxmin()
    match_indices = list(set(best_a_match_for_b).intersection(best_b_match_for_a))
    return match_indices
