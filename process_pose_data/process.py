import process_pose_data.local_io
import process_pose_data.honeycomb_io
import process_pose_data.analyze
import process_pose_data.track_poses
import process_pose_data.identify
import pandas as pd
import tqdm
from uuid import uuid4
import multiprocessing
import functools
import logging
import datetime
import time

logger = logging.getLogger(__name__)

def reconstruct_poses_3d_alphapose_local_by_time_segment(
    start,
    end,
    base_dir,
    environment_id,
    pose_model_id,
    room_x_limits,
    room_y_limits,
    camera_assignment_ids=None,
    camera_device_id_lookup=None,
    camera_calibrations=None,
    coordinate_space_id=None,
    client=None,
    uri=None,
    token_uri=None,
    audience=None,
    client_id=None,
    client_secret=None,
    alphapose_subdirectory='prepared',
    poses_2d_file_name='alphapose-results.json',
    poses_2d_json_format='cmu',
    pose_processing_subdirectory='pose_processing',
    poses_3d_directory_name='poses_3d',
    poses_3d_file_name_stem='poses_3d',
    pose_reconstruction_3d_metadata_filename_stem='pose_reconstruction_3d_metadata',
    min_keypoint_quality=None,
    min_num_keypoints=None,
    min_pose_quality=None,
    min_pose_pair_score=None,
    max_pose_pair_score=25.0,
    pose_pair_score_distance_method='pixels',
    pose_pair_score_pixel_distance_scale=5.0,
    pose_pair_score_summary_method='rms',
    pose_3d_limits=None,
    pose_3d_graph_initial_edge_threshold=2,
    pose_3d_graph_max_dispersion=0.20,
    include_track_labels=False,
    parallel=False,
    num_parallel_processes=None,
    progress_bar=False,
    notebook=False
):
    if start.tzinfo is None:
        logger.info('Specified start is timezone-naive. Assuming UTC')
        start=start.replace(tzinfo=datetime.timezone.utc)
    if end.tzinfo is None:
        logger.info('Specified end is timezone-naive. Assuming UTC')
        end=end.replace(tzinfo=datetime.timezone.utc)
    logger.info('Reconstructing 3D poses from local 2D pose data. Base directory: {}. Alphapose data subdirectory: {}. Pose processing data subdirectory: {}. Environment ID: {}. Start: {}. End: {}'.format(
        base_dir,
        alphapose_subdirectory,
        pose_processing_subdirectory,
        environment_id,
        start,
        end
    ))
    logger.info('Generating metadata')
    pose_reconstruction_3d_metadata = generate_pose_reconstruction_3d_metadata(
        start=start,
        end=end,
        environment_id=environment_id,
        pose_model_id=pose_model_id,
        room_x_limits=room_x_limits,
        room_y_limits=room_y_limits,
        camera_assignment_ids=camera_assignment_ids,
        camera_device_id_lookup=camera_device_id_lookup,
        camera_calibrations=camera_calibrations,
        coordinate_space_id=coordinate_space_id,
        poses_2d_json_format=poses_2d_json_format,
        min_keypoint_quality=min_keypoint_quality,
        min_num_keypoints=min_num_keypoints,
        min_pose_quality=min_pose_quality,
        min_pose_pair_score=min_pose_pair_score,
        max_pose_pair_score=max_pose_pair_score,
        pose_pair_score_distance_method=pose_pair_score_distance_method,
        pose_pair_score_pixel_distance_scale=pose_pair_score_pixel_distance_scale,
        pose_pair_score_summary_method=pose_pair_score_summary_method,
        pose_3d_limits=pose_3d_limits,
        pose_3d_graph_initial_edge_threshold=pose_3d_graph_initial_edge_threshold,
        pose_3d_graph_max_dispersion=pose_3d_graph_max_dispersion,
        include_track_labels=include_track_labels,
        client=client,
        uri=uri,
        token_uri=token_uri,
        audience=audience,
        client_id=client_id,
        client_secret=client_secret
    )
    inference_id_local = pose_reconstruction_3d_metadata.get('inference_execution').get('inference_id_local')
    camera_assignment_ids = pose_reconstruction_3d_metadata.get('camera_assignment_ids')
    camera_device_id_lookup = pose_reconstruction_3d_metadata.get('camera_device_id_lookup')
    camera_device_ids = pose_reconstruction_3d_metadata.get('camera_device_ids')
    camera_calibrations = pose_reconstruction_3d_metadata.get('camera_calibrations')
    pose_3d_limits = pose_reconstruction_3d_metadata.get('pose_3d_limits')
    logger.info('Writing inference metadata to local file')
    process_pose_data.local_io.write_metadata_local(
        metadata=pose_reconstruction_3d_metadata,
        base_dir=base_dir,
        environment_id=environment_id,
        output_subdirectory_name=poses_3d_directory_name,
        metadata_filename_stem=pose_reconstruction_3d_metadata_filename_stem,
        pose_processing_subdirectory=pose_processing_subdirectory
    )
    logger.info('Generating list of time segments')
    time_segment_start_list = process_pose_data.local_io.generate_time_segment_start_list(
        start=start,
        end=end
    )
    num_time_segments = len(time_segment_start_list)
    num_minutes = (end - start).total_seconds()/60
    logger.info('Reconstructing 3D poses for {} time segments spanning {:.3f} minutes: {} to {}'.format(
        num_time_segments,
        num_minutes,
        time_segment_start_list[0].isoformat(),
        time_segment_start_list[-1].isoformat()
    ))
    reconstruct_poses_3d_alphapose_local_time_segment_partial = functools.partial(
        reconstruct_poses_3d_alphapose_local_time_segment,
        base_dir=base_dir,
        environment_id=environment_id,
        inference_id_local=inference_id_local,
        alphapose_subdirectory=alphapose_subdirectory,
        poses_2d_file_name=poses_2d_file_name,
        poses_2d_json_format=poses_2d_json_format,
        pose_processing_subdirectory=pose_processing_subdirectory,
        poses_3d_directory_name=poses_3d_directory_name,
        poses_3d_file_name_stem=poses_3d_file_name_stem,
        camera_device_id_lookup=camera_device_id_lookup,
        client=None,
        uri=None,
        token_uri=None,
        audience=None,
        client_id=None,
        client_secret=None,
        pose_model_id=None,
        camera_calibrations=camera_calibrations,
        min_keypoint_quality=min_keypoint_quality,
        min_num_keypoints=min_num_keypoints,
        min_pose_quality=min_pose_quality,
        min_pose_pair_score=min_pose_pair_score,
        max_pose_pair_score=max_pose_pair_score,
        pose_pair_score_distance_method=pose_pair_score_distance_method,
        pose_pair_score_pixel_distance_scale=pose_pair_score_pixel_distance_scale,
        pose_pair_score_summary_method=pose_pair_score_summary_method,
        pose_3d_limits=pose_3d_limits,
        room_x_limits=room_x_limits,
        room_y_limits=room_y_limits,
        pose_3d_graph_initial_edge_threshold=pose_3d_graph_initial_edge_threshold,
        pose_3d_graph_max_dispersion=pose_3d_graph_max_dispersion,
        include_track_labels=include_track_labels,
        progress_bar=progress_bar,
        notebook=notebook
    )
    if progress_bar and parallel and ~notebook:
        logger.warning('Progress bars may not display properly with parallel processing enabled outside of a notebook')
    processing_start = time.time()
    if parallel:
        logger.info('Attempting to launch parallel processes')
        if num_parallel_processes is None:
            num_cpus=multiprocessing.cpu_count()
            num_processes = num_cpus - 1
            logger.info('Number of parallel processes not specified. {} CPUs detected. Launching {} processes'.format(
                num_cpus,
                num_processes
            ))
        with multiprocessing.Pool(num_processes) as p:
            poses_3d_df_list = p.map(reconstruct_poses_3d_alphapose_local_time_segment_partial, time_segment_start_list)
    else:
        poses_3d_df_list = list(map(reconstruct_poses_3d_alphapose_local_time_segment_partial, time_segment_start_list))
    processing_time = time.time() - processing_start
    logger.info('Processed {:.3f} minutes of 2D poses in {:.3f} minutes (ratio of {:.3f})'.format(
        num_minutes,
        processing_time/60,
        (processing_time/60)/num_minutes
    ))
    return inference_id_local

def reconstruct_poses_3d_alphapose_local_time_segment(
    time_segment_start,
    base_dir,
    environment_id,
    inference_id_local,
    alphapose_subdirectory='prepared',
    poses_2d_file_name='alphapose-results.json',
    poses_2d_json_format='cmu',
    pose_processing_subdirectory='pose_processing',
    poses_3d_directory_name='poses_3d',
    poses_3d_file_name_stem='poses_3d',
    camera_device_id_lookup=None,
    client=None,
    uri=None,
    token_uri=None,
    audience=None,
    client_id=None,
    client_secret=None,
    pose_model_id=None,
    camera_calibrations=None,
    min_keypoint_quality=None,
    min_num_keypoints=None,
    min_pose_quality=None,
    min_pose_pair_score=None,
    max_pose_pair_score=25.0,
    pose_pair_score_distance_method='pixels',
    pose_pair_score_pixel_distance_scale=5.0,
    pose_pair_score_summary_method='rms',
    pose_3d_limits=None,
    room_x_limits=None,
    room_y_limits=None,
    pose_3d_graph_initial_edge_threshold=2,
    pose_3d_graph_max_dispersion=0.20,
    include_track_labels=False,
    progress_bar=False,
    notebook=False
):
    logger.info('Processing 2D poses from local Alphapose output files for time segment starting at {}'.format(time_segment_start.isoformat()))
    logger.info('Fetching 2D pose data for time segment starting at {}'.format(time_segment_start.isoformat()))
    poses_2d_df_time_segment = process_pose_data.local_io.fetch_2d_pose_data_alphapose_local_time_segment(
        base_dir=base_dir,
        environment_id=environment_id,
        time_segment_start=time_segment_start,
        alphapose_subdirectory=alphapose_subdirectory,
        file_name=poses_2d_file_name,
        json_format=poses_2d_json_format
    )
    if len(poses_2d_df_time_segment) == 0:
        logger.info('No 2D poses found for time segment starting at %s', time_segment_start.isoformat())
        return
    logger.info('Fetched 2D pose data for time segment starting at {}'.format(time_segment_start.isoformat()))
    logger.info('Converting camera assignment IDs to camera device IDs for time segment starting at {}'.format(time_segment_start.isoformat()))
    poses_2d_df_time_segment = process_pose_data.local_io.convert_assignment_ids_to_camera_device_ids(
        poses_2d_df=poses_2d_df_time_segment,
        camera_device_id_lookup=camera_device_id_lookup,
        client=client,
        uri=uri,
        token_uri=token_uri,
        audience=audience,
        client_id=client_id,
        client_secret=client_secret
    )
    logger.info('Converted camera assignment IDs to camera device IDs for time segment starting at {}'.format(time_segment_start.isoformat()))
    logger.info('Reconstructing 3D poses for time segment starting at {}'.format(time_segment_start.isoformat()))
    poses_3d_local_ids_df = process_pose_data.analyze.reconstruct_poses_3d(
        poses_2d_df=poses_2d_df_time_segment,
        pose_2d_id_column_name='pose_2d_id_local',
        pose_2d_ids_column_name='pose_2d_ids_local',
        pose_model_id=pose_model_id,
        camera_calibrations=camera_calibrations,
        min_keypoint_quality=min_keypoint_quality,
        min_num_keypoints=min_num_keypoints,
        min_pose_quality=min_pose_quality,
        min_pose_pair_score=min_pose_pair_score,
        max_pose_pair_score=max_pose_pair_score,
        pose_pair_score_distance_method=pose_pair_score_distance_method,
        pose_pair_score_pixel_distance_scale=pose_pair_score_pixel_distance_scale,
        pose_pair_score_summary_method=pose_pair_score_summary_method,
        pose_3d_limits=pose_3d_limits,
        room_x_limits=room_x_limits,
        room_y_limits=room_y_limits,
        pose_3d_graph_initial_edge_threshold=pose_3d_graph_initial_edge_threshold,
        pose_3d_graph_max_dispersion=pose_3d_graph_max_dispersion,
        include_track_labels=include_track_labels,
        progress_bar=progress_bar,
        notebook=notebook
    )
    logger.info('Reconstructed 3D poses for time segment starting at {}'.format(time_segment_start.isoformat()))
    logger.info('Writing 3D poses to disk for time segment starting at {}'.format(time_segment_start.isoformat()))
    process_pose_data.local_io.write_3d_pose_data_local_time_segment(
        poses_3d_df=poses_3d_local_ids_df,
        base_dir=base_dir,
        environment_id=environment_id,
        time_segment_start=time_segment_start,
        inference_id_local=inference_id_local,
        pose_processing_subdirectory=pose_processing_subdirectory,
        poses_3d_directory_name=poses_3d_directory_name,
        poses_3d_file_name_stem=poses_3d_file_name_stem
    )

def generate_pose_tracks_3d_local_by_time_segment(
    start,
    end,
    base_dir,
    environment_id,
    pose_reconstruction_3d_inference_id,
    max_match_distance=1.0,
    max_iterations_since_last_match=20,
    centroid_position_initial_sd=1.0,
    centroid_velocity_initial_sd=1.0,
    reference_delta_t_seconds=1.0,
    reference_velocity_drift=0.30,
    position_observation_sd=0.5,
    num_poses_per_track_min=11,
    pose_processing_subdirectory='pose_processing',
    poses_3d_directory_name='poses_3d',
    poses_3d_file_name_stem='poses_3d',
    pose_tracks_3d_directory_name='pose_tracks_3d',
    pose_tracks_3d_file_name_stem='pose_tracks_3d',
    pose_tracking_3d_metadata_filename_stem='pose_tracking_3d_metadata',
    progress_bar=False,
    notebook=False
):
    if start.tzinfo is None:
        logger.info('Specified start is timezone-naive. Assuming UTC')
        start=start.replace(tzinfo=datetime.timezone.utc)
    if end.tzinfo is None:
        logger.info('Specified end is timezone-naive. Assuming UTC')
        end=end.replace(tzinfo=datetime.timezone.utc)
    logger.info('Generating 3D pose tracks from local 3D pose data. Base directory: {}. Pose processing data subdirectory: {}. Environment ID: {}. Start: {}. End: {}'.format(
        base_dir,
        pose_processing_subdirectory,
        environment_id,
        start,
        end
    ))
    logger.info('Generating metadata')
    pose_tracking_3d_metadata = generate_pose_tracking_3d_metadata(
        start=start,
        end=end,
        environment_id=environment_id,
        pose_reconstruction_3d_inference_id=pose_reconstruction_3d_inference_id,
        max_match_distance=max_match_distance,
        max_iterations_since_last_match=max_iterations_since_last_match,
        centroid_position_initial_sd=centroid_position_initial_sd,
        centroid_velocity_initial_sd=None,
        reference_delta_t_seconds=reference_delta_t_seconds,
        reference_velocity_drift=reference_velocity_drift,
        position_observation_sd=position_observation_sd
    )
    pose_tracking_3d_inference_id_local = pose_tracking_3d_metadata.get('inference_execution').get('inference_id_local')
    logger.info('Writing inference metadata to local file')
    process_pose_data.local_io.write_metadata_local(
        metadata=pose_tracking_3d_metadata,
        base_dir=base_dir,
        environment_id=environment_id,
        output_subdirectory_name=pose_tracks_3d_directory_name,
        metadata_filename_stem=pose_tracking_3d_metadata_filename_stem,
        pose_processing_subdirectory=pose_processing_subdirectory
    )
    logger.info('Generating list of time segments')
    time_segment_start_list = process_pose_data.local_io.generate_time_segment_start_list(
        start=start,
        end=end
    )
    num_time_segments = len(time_segment_start_list)
    num_minutes = (end - start).total_seconds()/60
    logger.info('Tracking 3D poses for {} time segments spanning {:.3f} minutes: {} to {}'.format(
        num_time_segments,
        num_minutes,
        time_segment_start_list[0].isoformat(),
        time_segment_start_list[-1].isoformat()
    ))
    processing_start = time.time()
    pose_tracks_3d = None
    if progress_bar:
        if notebook:
            time_segment_start_iterator = tqdm.notebook.tqdm(time_segment_start_list)
        else:
            time_segment_start_iterator = tqdm.tqdm(time_segment_start_list)
    else:
        time_segment_start_iterator = time_segment_start_list
    for time_segment_start in time_segment_start_iterator:
        poses_3d_df = process_pose_data.local_io.fetch_3d_pose_data_local_time_segment(
            time_segment_start=time_segment_start,
            base_dir=base_dir,
            environment_id=environment_id,
            inference_id_local=pose_reconstruction_3d_inference_id,
            pose_processing_subdirectory=pose_processing_subdirectory,
            poses_3d_directory_name=poses_3d_directory_name,
            poses_3d_file_name_stem=poses_3d_file_name_stem
        )
        if len(poses_3d_df) == 0:
            continue
        pose_tracks_3d =  process_pose_data.track_poses.update_pose_tracks_3d(
            poses_3d_df=poses_3d_df,
            pose_tracks_3d=pose_tracks_3d,
            max_match_distance=max_match_distance,
            max_iterations_since_last_match=max_iterations_since_last_match,
            centroid_position_initial_sd=centroid_position_initial_sd,
            centroid_velocity_initial_sd=centroid_velocity_initial_sd,
            reference_delta_t_seconds=reference_delta_t_seconds,
            reference_velocity_drift=reference_velocity_drift,
            position_observation_sd=position_observation_sd,
            progress_bar=False,
            notebook=False
        )
    if num_poses_per_track_min is not None:
        pose_tracks_3d.filter(
            num_poses_min=num_poses_per_track_min,
            inplace=True
        )
    process_pose_data.local_io.write_3d_pose_track_data_local(
        pose_tracks_3d=pose_tracks_3d.output(),
        base_dir=base_dir,
        environment_id=environment_id,
        inference_id_local=pose_tracking_3d_inference_id_local,
        pose_processing_subdirectory=pose_processing_subdirectory,
        pose_tracks_3d_directory_name=pose_tracks_3d_directory_name,
        pose_tracks_3d_file_name_stem=pose_tracks_3d_file_name_stem
    )
    processing_time = time.time() - processing_start
    logger.info('Processed {:.3f} minutes of 3D poses in {:.3f} minutes (ratio of {:.3f})'.format(
        num_minutes,
        processing_time/60,
        (processing_time/60)/num_minutes
    ))
    return pose_tracking_3d_inference_id_local

def interpolate_pose_tracks_3d_local_by_pose_track(
    base_dir,
    environment_id,
    pose_tracking_3d_inference_id,
    pose_processing_subdirectory='pose_processing',
    poses_3d_directory_name='poses_3d',
    poses_3d_file_name_stem='poses_3d',
    pose_tracks_3d_directory_name='pose_tracks_3d',
    pose_tracks_3d_file_name_stem='pose_tracks_3d',
    pose_tracking_3d_metadata_filename_stem='pose_tracking_3d_metadata',
    pose_track_3d_interpolation_directory_name='pose_track_3d_interpolation',
    pose_track_3d_interpolation_metadata_filename_stem='pose_track_3d_interpolation_metadata',
    progress_bar=False,
    notebook=False
):
    logger.info('Interpolating 3D pose tracks from local 3D pose track data and local 3D pose data. Base directory: {}. Pose processing data subdirectory: {}. Environment ID: {}.'.format(
        base_dir,
        pose_processing_subdirectory,
        environment_id
    ))
    logger.info('Generating metadata')
    pose_track_3d_interpolation_metadata = generate_pose_track_3d_interpolation_metadata(
        base_dir=base_dir,
        environment_id=environment_id,
        pose_tracking_3d_inference_id=pose_tracking_3d_inference_id,
        pose_processing_subdirectory=pose_processing_subdirectory,
        pose_tracks_3d_directory_name=pose_tracks_3d_directory_name,
        pose_tracking_3d_metadata_filename_stem=pose_tracking_3d_metadata_filename_stem,
    )
    pose_reconstruction_3d_inference_id_local = pose_track_3d_interpolation_metadata['pose_reconstruction_3d_inference_id']
    pose_tracking_3d_inference_id_local = pose_track_3d_interpolation_metadata['pose_tracking_3d_inference_id']
    pose_track_3d_interpolation_inference_id_local = pose_track_3d_interpolation_metadata.get('inference_execution').get('inference_id_local')
    logger.info('Writing inference metadata to local file')
    process_pose_data.local_io.write_metadata_local(
        metadata=pose_track_3d_interpolation_metadata,
        base_dir=base_dir,
        environment_id=environment_id,
        output_subdirectory_name=pose_track_3d_interpolation_directory_name,
        metadata_filename_stem=pose_track_3d_interpolation_metadata_filename_stem,
        pose_processing_subdirectory=pose_processing_subdirectory,
    )
    pose_tracks_3d = process_pose_data.local_io.fetch_3d_pose_track_data_local(
        base_dir=base_dir,
        environment_id=environment_id,
        inference_id_local=pose_tracking_3d_inference_id_local,
        pose_processing_subdirectory=pose_processing_subdirectory,
        pose_tracks_3d_directory_name=pose_tracks_3d_directory_name,
        pose_tracks_3d_file_name_stem=pose_tracks_3d_file_name_stem
    )
    num_pose_tracks = len(pose_tracks_3d)
    pose_tracks_start = min([pose_track_3d['start'] for pose_track_3d in pose_tracks_3d.values()])
    pose_tracks_end = max([pose_track_3d['end'] for pose_track_3d in pose_tracks_3d.values()])
    num_poses = sum([len(pose_track_3d['pose_3d_ids']) for pose_track_3d in pose_tracks_3d.values()])
    num_minutes = (pose_tracks_end - pose_tracks_start).total_seconds()/60
    logger.info('Interpolating {} 3D pose tracks spanning {} poses and {:.3f} minutes: {} to {}'.format(
        num_pose_tracks,
        num_poses,
        num_minutes,
        pose_tracks_start.isoformat(),
        pose_tracks_end.isoformat()
    ))
    processing_start = time.time()
    if progress_bar:
        if notebook:
            pose_track_iterator = tqdm.notebook.tqdm(pose_tracks_3d.items())
        else:
            pose_track_iterator = tqdm.tqdm(pose_tracks_3d.items())
    else:
        pose_track_iterator = pose_tracks_3d.items()
    pose_tracks_3d_new = dict()
    for pose_track_3d_id, pose_track_3d in pose_track_iterator:
        pose_track_start = pose_track_3d['start']
        pose_track_end = pose_track_3d['end']
        pose_3d_ids = pose_track_3d['pose_3d_ids']
        poses_3d_in_track_df = process_pose_data.fetch_3d_pose_data_local(
            start=pose_track_start,
            end=pose_track_end,
            base_dir=base_dir,
            environment_id=environment_id,
            inference_id_local=pose_reconstruction_3d_inference_id_local,
            pose_3d_ids=pose_3d_ids,
            pose_processing_subdirectory=pose_processing_subdirectory,
            poses_3d_directory_name=poses_3d_directory_name,
            poses_3d_file_name_stem=poses_3d_file_name_stem
        )
        poses_3d_new_df = process_pose_data.interpolate_pose_track(poses_3d_in_track_df)
        if len(poses_3d_new_df) == 0:
            continue
        process_pose_data.write_3d_pose_data_local(
            poses_3d_df=poses_3d_new_df,
            base_dir=base_dir,
            environment_id=environment_id,
            inference_id_local=pose_track_3d_interpolation_inference_id_local,
            append=True,
            pose_processing_subdirectory=pose_processing_subdirectory,
            poses_3d_directory_name=poses_3d_directory_name,
            poses_3d_file_name_stem=poses_3d_file_name_stem
        )
        pose_tracks_3d_new[pose_track_3d_id] = {
            'start': pd.to_datetime(poses_3d_new_df['timestamp'].min()).to_pydatetime(),
            'end': pd.to_datetime(poses_3d_new_df['timestamp'].max()).to_pydatetime(),
            'pose_3d_ids': poses_3d_new_df.index.tolist()
        }
    process_pose_data.write_3d_pose_track_data_local(
        pose_tracks_3d=pose_tracks_3d_new,
        base_dir=base_dir,
        environment_id=environment_id,
        inference_id_local=pose_track_3d_interpolation_inference_id_local,
        pose_processing_subdirectory=pose_processing_subdirectory,
        pose_tracks_3d_directory_name=pose_tracks_3d_directory_name,
        pose_tracks_3d_file_name_stem=pose_tracks_3d_file_name_stem
    )
    processing_time = time.time() - processing_start
    logger.info('Processed {} 3D pose tracks in {:.3f} minutes'.format(
        num_pose_tracks,
        processing_time/60
    ))
    return pose_track_3d_interpolation_inference_id_local

def download_position_data_by_datapoint(
    datapoint_timestamp_min,
    datapoint_timestamp_max,
    start,
    end,
    base_dir,
    environment_id,
    pose_processing_subdirectory='pose_processing',
    position_data_directory_name='position_data',
    position_data_file_name_stem='position_data',
    download_position_data_metadata_filename_stem='download_position_data_metadata',
    chunk_size=100,
    client=None,
    uri=None,
    token_uri=None,
    audience=None,
    client_id=None,
    client_secret=None,
    progress_bar=False,
    notebook=False
):
    if datapoint_timestamp_min.tzinfo is None:
        logger.info('Specified minimum datapoint timestamp is timezone-naive. Assuming UTC')
        datapoint_timestamp_min=datapoint_timestamp_min.replace(tzinfo=datetime.timezone.utc)
    if datapoint_timestamp_max.tzinfo is None:
        logger.info('Specified maximum datapoint timestamp is timezone-naive. Assuming UTC')
        datapoint_timestamp_max=datapoint_timestamp_max.replace(tzinfo=datetime.timezone.utc)
    if start.tzinfo is None:
        logger.info('Specified start is timezone-naive. Assuming UTC')
        start=start.replace(tzinfo=datetime.timezone.utc)
    if end.tzinfo is None:
        logger.info('Specified end is timezone-naive. Assuming UTC')
        end=end.replace(tzinfo=datetime.timezone.utc)
    logger.info('Downloading person position data from Honeycomb. Base directory: {}. Pose processing data subdirectory: {}. Environment ID: {}. Start: {}. End: {}'.format(
        base_dir,
        pose_processing_subdirectory,
        environment_id,
        start,
        end
    ))
    processing_start = time.time()
    logger.info('Generating metadata')
    download_position_data_metadata = generate_download_position_data_metadata(
        datapoint_timestamp_min=datapoint_timestamp_min,
        datapoint_timestamp_max=datapoint_timestamp_max,
        start=start,
        end=end,
        environment_id=environment_id
    )
    download_position_data_inference_id_local = download_position_data_metadata.get('inference_execution').get('inference_id_local')
    logger.info('Writing inference metadata to local file')
    process_pose_data.local_io.write_metadata_local(
        metadata=download_position_data_metadata,
        base_dir=base_dir,
        environment_id=environment_id,
        output_subdirectory_name=position_data_directory_name,
        metadata_filename_stem=download_position_data_metadata_filename_stem,
        pose_processing_subdirectory=pose_processing_subdirectory
    )
    logger.info('Generating list of time segments')
    time_segment_start_list = process_pose_data.local_io.generate_time_segment_start_list(
        start=start,
        end=end
    )
    num_time_segments = len(time_segment_start_list)
    num_minutes = (end - start).total_seconds()/60
    logger.info('Downloading position data for {} time segments spanning {:.3f} minutes: {} to {}'.format(
        num_time_segments,
        num_minutes,
        time_segment_start_list[0].isoformat(),
        time_segment_start_list[-1].isoformat()
    ))
    logger.info('Fetching person tag info from Honeycomb for specified environment and time span')
    person_tag_info_df = process_pose_data.honeycomb_io.fetch_person_tag_info(
        start=start,
        end=end,
        environment_id=environment_id,
        chunk_size=chunk_size,
        client=client,
        uri=uri,
        token_uri=token_uri,
        audience=audience,
        client_id=client_id,
        client_secret=client_secret
    )
    assignment_ids = person_tag_info_df.index.tolist()
    logger.info('Found {} tags for specified environment and time span'.format(
        len(assignment_ids)
    ))
    logger.info('Fetching UWB datapoint IDs for these tags and specified datapoint timestamp min/max')
    data_ids = process_pose_data.honeycomb_io.fetch_uwb_data_ids(
        datapoint_timestamp_min=datapoint_timestamp_min,
        datapoint_timestamp_max=datapoint_timestamp_max,
        assignment_ids=assignment_ids,
        chunk_size=chunk_size,
        client=None,
        uri=None,
        token_uri=None,
        audience=None,
        client_id=None,
        client_secret=None
    )
    logger.info('Found {} UWB datapoint IDs for these tags and specified datapoint timestamp min/max'.format(
        len(data_ids)
    ))
    logger.info('Fetching position data from each of these UWB datapoints and writing to local files')
    if progress_bar:
        if notebook:
            data_id_iterator = tqdm.notebook.tqdm(data_ids)
        else:
            data_id_iterator = tqdm.tqdm(data_ids)
    else:
        data_id_iterator = data_ids
    for data_id in data_id_iterator:
        position_data_df = process_pose_data.honeycomb_io.fetch_uwb_data_data_id(
            data_id=data_id,
            client=None,
            uri=None,
            token_uri=None,
            audience=None,
            client_id=None,
            client_secret=None
        )
        if len(position_data_df) == 0:
            continue
        position_data_df = process_pose_data.honeycomb_io.extract_position_data(
            df=position_data_df
        )
        if len(position_data_df) == 0:
            continue
        position_data_df = process_pose_data.identify.resample_uwb_data(
            uwb_data_df=position_data_df,
            id_field_names=[
                'assignment_id',
                'object_id',
                'serial_number',
            ],
            interpolation_field_names=[
                'x_position',
                'y_position',
                'z_position'
            ],
            timestamp_field_name='timestamp'
        )
        position_data_df = process_pose_data.honeycomb_io.add_person_tag_info(
            uwb_data_df=position_data_df,
            person_tag_info_df=person_tag_info_df
        )
        for time_segment_start in time_segment_start_list:
            position_data_time_segment_df = position_data_df.loc[
                (position_data_df['timestamp'] >= time_segment_start) &
                (position_data_df['timestamp'] < time_segment_start + datetime.timedelta(seconds=10))
            ].reset_index(drop=True)
            if len(position_data_time_segment_df) == 0:
                continue
            process_pose_data.local_io.write_position_data_local_time_segment(
                position_data_df=position_data_time_segment_df,
                base_dir=base_dir,
                environment_id=environment_id,
                time_segment_start=time_segment_start,
                inference_id_local=download_position_data_inference_id_local,
                append=True,
                pose_processing_subdirectory=pose_processing_subdirectory,
                position_data_directory_name=position_data_directory_name,
                position_data_file_name_stem=position_data_file_name_stem
            )
    processing_time = time.time() - processing_start
    logger.info('Downloaded {:.3f} minutes of position data in {:.3f} minutes (ratio of {:.3f})'.format(
        num_minutes,
        processing_time/60,
        (processing_time/60)/num_minutes
    ))
    return download_position_data_inference_id_local

def identify_pose_tracks_3d_local_by_segment(
    start,
    end,
    base_dir,
    environment_id,
    download_position_data_inference_id,
    pose_track_3d_interpolation_inference_id,
    sensor_position_keypoint_index=10,
    active_person_ids=None,
    return_match_statistics=False,
    pose_processing_subdirectory='pose_processing',
    position_data_directory_name='position_data',
    position_data_file_name_stem='position_data',
    poses_3d_directory_name='poses_3d',
    poses_3d_file_name_stem='poses_3d',
    pose_tracks_3d_directory_name='pose_tracks_3d',
    pose_tracks_3d_file_name_stem='pose_tracks_3d',
    pose_track_3d_interpolation_directory_name='pose_track_3d_interpolation',
    pose_track_3d_interpolation_metadata_filename_stem='pose_track_3d_interpolation_metadata',
    pose_track_3d_identification_directory_name='pose_track_3d_identification',
    pose_track_3d_identification_file_name_stem='pose_track_3d_identification',
    pose_track_3d_identification_metadata_filename_stem='pose_track_3d_identification_metadata',
    progress_bar=False,
    notebook=False
):
    logger.info('Identifying 3D pose tracks from local interpolated 3D pose track data and local UWB position data. Base directory: {}. Pose processing data subdirectory: {}. Environment ID: {}.'.format(
        base_dir,
        pose_processing_subdirectory,
        environment_id
    ))
    processing_start = time.time()
    logger.info('Generating metadata')
    pose_track_3d_identification_metadata = generate_pose_track_3d_identification_metadata(
        base_dir=base_dir,
        environment_id=environment_id,
        pose_track_3d_interpolation_inference_id=pose_track_3d_interpolation_inference_id,
        pose_processing_subdirectory=pose_processing_subdirectory,
        pose_track_3d_interpolation_directory_name=pose_track_3d_interpolation_directory_name,
        pose_track_3d_interpolation_metadata_filename_stem=pose_track_3d_interpolation_metadata_filename_stem,
    )
    logger.info('Writing inference metadata to local file')
    process_pose_data.local_io.write_metadata_local(
        metadata=pose_track_3d_identification_metadata,
        base_dir=base_dir,
        environment_id=environment_id,
        output_subdirectory_name=pose_track_3d_identification_directory_name,
        metadata_filename_stem=pose_track_3d_identification_metadata_filename_stem,
        pose_processing_subdirectory=pose_processing_subdirectory
    )
    pose_track_3d_identification_inference_id_local = pose_track_3d_identification_metadata['inference_execution']['inference_id_local']
    pose_reconstruction_3d_inference_id_local = pose_track_3d_identification_metadata['pose_reconstruction_3d_inference_id']
    pose_tracking_3d_inference_id_local = pose_track_3d_identification_metadata['pose_tracking_3d_inference_id']
    # Fetch pose track data
    pose_tracks_3d_before_interpolation = process_pose_data.local_io.fetch_3d_pose_track_data_local(
        base_dir=base_dir,
        environment_id=environment_id,
        inference_id_local=pose_tracking_3d_inference_id_local,
        pose_processing_subdirectory=pose_processing_subdirectory,
        pose_tracks_3d_directory_name=pose_tracks_3d_directory_name,
        pose_tracks_3d_file_name_stem=pose_tracks_3d_file_name_stem
    )
    pose_tracks_3d_from_interpolation = process_pose_data.local_io.fetch_3d_pose_track_data_local(
        base_dir=base_dir,
        environment_id=environment_id,
        inference_id_local=pose_track_3d_interpolation_inference_id,
        pose_processing_subdirectory=pose_processing_subdirectory,
        pose_tracks_3d_directory_name=pose_tracks_3d_directory_name,
        pose_tracks_3d_file_name_stem=pose_tracks_3d_file_name_stem
    )
    pose_3d_ids_with_tracks_before_interpolation_df = process_pose_data.track_poses.convert_pose_tracks_3d_to_df(
        pose_tracks_3d=pose_tracks_3d_before_interpolation
    )
    pose_3d_ids_with_tracks_from_interpolation_df = process_pose_data.track_poses.convert_pose_tracks_3d_to_df(
        pose_tracks_3d=pose_tracks_3d_from_interpolation
    )
    pose_3d_ids_with_tracks_df = pd.concat(
        (pose_3d_ids_with_tracks_before_interpolation_df, pose_3d_ids_with_tracks_from_interpolation_df)
    ).sort_values('pose_track_3d_id')
    logger.info('Generating list of time segments')
    time_segment_start_list = process_pose_data.local_io.generate_time_segment_start_list(
        start=start,
        end=end
    )
    num_time_segments = len(time_segment_start_list)
    num_minutes = (end - start).total_seconds()/60
    logger.info('Identifying pose tracks for {} time segments spanning {:.3f} minutes: {} to {}'.format(
        num_time_segments,
        num_minutes,
        time_segment_start_list[0].isoformat(),
        time_segment_start_list[-1].isoformat()
    ))
    if progress_bar:
        if notebook:
            time_segment_start_iterator = tqdm.notebook.tqdm(time_segment_start_list)
        else:
            time_segment_start_iterator = tqdm.tqdm(time_segment_start_list)
    else:
        time_segment_start_iterator = time_segment_start_list
    pose_identification_time_segment_df_list = list()
    if return_match_statistics:
        match_statistics_time_segment_df_list = list()
    for time_segment_start in time_segment_start_iterator:
        # Fetch 3D poses with tracks
        poses_3d_time_segment_df = process_pose_data.local_io.fetch_3d_pose_data_local_time_segment(
            time_segment_start=time_segment_start,
            base_dir=base_dir,
            environment_id=environment_id,
            inference_id_local=[
                pose_reconstruction_3d_inference_id_local,
                pose_track_3d_interpolation_inference_id
            ],
            pose_processing_subdirectory=pose_processing_subdirectory,
            poses_3d_directory_name=poses_3d_directory_name,
            poses_3d_file_name_stem=poses_3d_file_name_stem
        )
        poses_3d_with_tracks_time_segment_df = poses_3d_time_segment_df.join(pose_3d_ids_with_tracks_df, how='inner')
        # Add sensor positions
        poses_3d_with_tracks_and_sensor_positions_time_segment_df = process_pose_data.identify.extract_sensor_position_data(
            poses_3d_with_tracks_df=poses_3d_with_tracks_time_segment_df,
            sensor_position_keypoint_index=sensor_position_keypoint_index
        )
        # Fetch resampled UWB data
        uwb_data_resampled_time_segment_df = process_pose_data.local_io.fetch_position_data_local_time_segment(
            time_segment_start=time_segment_start,
            base_dir=base_dir,
            environment_id=environment_id,
            inference_id_local=download_position_data_inference_id,
            pose_processing_subdirectory=pose_processing_subdirectory,
            position_data_directory_name=position_data_directory_name,
            position_data_file_name_stem=position_data_file_name_stem
        )
        # Identify poses
        if return_match_statistics:
            pose_identification_time_segment_df, match_statistics_time_segment_df = process_pose_data.identify.identify_poses(
                poses_3d_with_tracks_and_sensor_positions_df=poses_3d_with_tracks_and_sensor_positions_time_segment_df,
                uwb_data_resampled_df=uwb_data_resampled_time_segment_df,
                active_person_ids=active_person_ids,
                return_match_statistics=return_match_statistics
            )
            match_statistics_time_segment_df_list.append(match_statistics_time_segment_df)
        else:
            pose_identification_time_segment_df = process_pose_data.identify.identify_poses(
                poses_3d_with_tracks_and_sensor_positions_df=poses_3d_with_tracks_and_sensor_positions_time_segment_df,
                uwb_data_resampled_df=uwb_data_resampled_time_segment_df,
                active_person_ids=active_person_ids,
                return_match_statistics=return_match_statistics
            )
        # Add to list
        pose_identification_time_segment_df_list.append(pose_identification_time_segment_df)
    pose_identification_df = pd.concat(pose_identification_time_segment_df_list)
    pose_track_identification_df = process_pose_data.identify.identify_pose_tracks(
        pose_identification_df=pose_identification_df
    )
    process_pose_data.local_io.write_pose_track_3d_identification_data_local(
        pose_track_identification_df=pose_track_identification_df,
        base_dir=base_dir,
        environment_id=environment_id,
        inference_id_local=pose_track_3d_identification_inference_id_local,
        pose_processing_subdirectory=pose_processing_subdirectory,
        pose_track_3d_identification_directory_name=pose_track_3d_identification_directory_name,
        pose_track_3d_identification_file_name_stem=pose_track_3d_identification_file_name_stem
    )
    processing_time = time.time() - processing_start
    logger.info('Identified 3D pose tracks spanning {:.3f} {:.3f} minutes (ratio of {:.3f})'.format(
        num_minutes,
        processing_time/60,
        (processing_time/60)/num_minutes
    ))
    if return_match_statistics:
        match_statistics_df = pd.concat(match_statistics_time_segment_df_list)
        return pose_track_3d_identification_inference_id_local, match_statistics_df
    return pose_track_3d_identification_inference_id_local

def upload_3d_poses_honeycomb(
    inference_id_local,
    base_dir,
    environment_id,
    pose_processing_subdirectory='pose_processing',
    poses_3d_directory_name='poses_3d',
    poses_3d_file_name_stem='poses_3d',
    pose_reconstruction_3d_metadata_filename_stem='pose_reconstruction_3d_metadata',
    chunk_size=100,
    client=None,
    uri=None,
    token_uri=None,
    audience=None,
    client_id=None,
    client_secret=None,
    progress_bar=False,
    notebook=False
):
    pose_reconstruction_3d_metadata = process_pose_data.local_io.read_pose_reconstruction_3d_metadata_local(
        inference_id_local=inference_id_local,
        base_dir=base_dir,
        environment_id=environment_id,
        pose_processing_subdirectory=pose_processing_subdirectory,
        poses_3d_directory_name=poses_3d_directory_name,
        pose_reconstruction_3d_metadata_filename_stem=pose_reconstruction_3d_metadata_filename_stem
    )
    start = pose_reconstruction_3d_metadata.get('start')
    end = pose_reconstruction_3d_metadata.get('end')
    pose_model_id = pose_reconstruction_3d_metadata.get('pose_model_id')
    coordinate_space_id = pose_reconstruction_3d_metadata.get('coordinate_space_id')
    time_segment_start_list = process_pose_data.local_io.generate_time_segment_start_list(
        start=start,
        end=end
    )
    num_time_segments = len(time_segment_start_list)
    num_minutes = (end - start).total_seconds()/60
    logger.info('Uploading 3D poses to Honeycomb for {} time segments spanning {:.3f} minutes: {} to {}'.format(
        num_time_segments,
        num_minutes,
        time_segment_start_list[0].isoformat(),
        time_segment_start_list[-1].isoformat()
    ))
    pose_3d_ids=list()
    if progress_bar:
        if notebook:
            time_segment_start_iterator = tqdm.notebook.tqdm(time_segment_start_list)
        else:
            time_segment_start_iterator = tqdm.tqdm(time_segment_start_list)
    else:
        time_segment_start_iterator = time_segment_start_list
    pose_3d_ids=list()
    for time_segment_start in time_segment_start_iterator:
        poses_3d_df_time_segment = process_pose_data.local_io.fetch_3d_pose_data_local_time_segment(
            time_segment_start=time_segment_start,
            base_dir=base_dir,
            environment_id=environment_id,
            inference_id_local=inference_id_local,
            pose_processing_subdirectory=pose_processing_subdirectory,
            poses_3d_directory_name=poses_3d_directory_name,
            poses_3d_file_name_stem=poses_3d_file_name_stem
        )
        raise ValueError('We need a way of fetching Honeycomb inference ID before writing 3D pose data to Honeycomb')
        pose_3d_ids_time_segment = process_pose_data.honeycomb_io.write_3d_pose_data(
            poses_3d_df=poses_3d_df_time_segment,
            coordinate_space_id=coordinate_space_id,
            pose_model_id=pose_model_id,
            source_id=inference_id,
            source_type='INFERRED',
            chunk_size=chunk_size,
            uri=uri,
            token_uri=token_uri,
            audience=audience,
            client_id=client_id,
            client_secret=client_secret
        )
        pose_3d_ids.extend(pose_3d_ids_time_segment)
    return pose_3d_ids

def delete_reconstruct_3d_poses_output(
    base_dir,
    environment_id,
    inference_id_local,
    pose_processing_subdirectory='pose_processing',
    poses_3d_directory_name='poses_3d',
    poses_3d_file_name_stem='poses_3d',
    pose_reconstruction_3d_metadata_filename_stem='pose_reconstruction_3d_metadata',
    chunk_size=100,
    client=None,
    uri=None,
    token_uri=None,
    audience=None,
    client_id=None,
    client_secret=None
):
    logger.info('Deleting local 3D pose data')
    process_pose_data.local_io.delete_3d_pose_data_local(
        base_dir=base_dir,
        environment_id=environment_id,
        inference_id_local=inference_id_local,
        pose_processing_subdirectory=pose_processing_subdirectory,
        poses_3d_directory_name=poses_3d_directory_name,
        poses_3d_file_name_stem=poses_3d_file_name_stem
    )
    logger.info('Deleting local inference metadata')
    process_pose_data.local_io.delete_metadata_local(
        inference_id_local=inference_id_local,
        base_dir=base_dir,
        environment_id=environment_id,
        output_subdirectory_name=poses_3d_directory_name,
        metadata_filename_stem=pose_reconstruction_3d_metadata_filename_stem,
        pose_processing_subdirectory=pose_processing_subdirectory
    )
    logger.info('Deleting Honeycomb 3D pose data')
    raise ValueError('We need a way of fetching Honeycomb inference ID before deleting 3D pose data from Honeycomb')
    process_pose_data.honeycomb_io.delete_3d_pose_data_by_inference_id(
        inference_id=inference_id,
        chunk_size=chunk_size,
        client=client,
        uri=uri,
        token_uri=token_uri,
        audience=audience,
        client_id=client_id,
        client_secret=client_secret
    )
    logger.info('Deleting Honeycomb inference execution object')
    process_pose_data.honeycomb_io.delete_inference_execution(
        inference_id=inference_id,
        client=client,
        uri=uri,
        token_uri=token_uri,
        audience=audience,
        client_id=client_id,
        client_secret=client_secret
    )

def generate_pose_reconstruction_3d_metadata(
    start,
    end,
    environment_id,
    pose_model_id,
    room_x_limits,
    room_y_limits,
    camera_assignment_ids=None,
    camera_device_id_lookup=None,
    camera_calibrations=None,
    coordinate_space_id=None,
    poses_2d_json_format=None,
    min_keypoint_quality=None,
    min_num_keypoints=None,
    min_pose_quality=None,
    min_pose_pair_score=None,
    max_pose_pair_score=None,
    pose_pair_score_distance_method=None,
    pose_pair_score_pixel_distance_scale=None,
    pose_pair_score_summary_method=None,
    pose_3d_limits=None,
    pose_3d_graph_initial_edge_threshold=None,
    pose_3d_graph_max_dispersion=None,
    include_track_labels=None,
    client=None,
    uri=None,
    token_uri=None,
    audience=None,
    client_id=None,
    client_secret=None
):
    logger.info('Generating inference execution object')
    inference_execution = generate_pose_reconstruction_3d_inference_execution(
        environment_id,
        start,
        end
    )
    if camera_assignment_ids is None:
        logger.info('Camera assignment IDs not specified. Fetching camera assignment IDs from Honeycomb based on environmen and time span')
        camera_assignment_ids = process_pose_data.honeycomb_io.fetch_camera_assignment_ids_from_environment(
            start=start,
            end=end,
            environment_id=environment_id,
            uri=uri,
            token_uri=token_uri,
            audience=audience,
            client_id=client_id,
            client_secret=client_secret
        )
    if camera_device_id_lookup is None:
        logger.info('Camera device ID lookup table not specified. Fetching camera device ID info from Honeycomb based on camera assignment IDs')
        camera_device_id_lookup = process_pose_data.honeycomb_io.fetch_camera_device_id_lookup(
            assignment_ids=camera_assignment_ids,
            client=client,
            uri=uri,
            token_uri=token_uri,
            audience=audience,
            client_id=client_id,
            client_secret=client_secret
        )
    camera_device_ids = list(camera_device_id_lookup.values())
    if camera_calibrations is None:
        logger.info('Camera calibration parameters not specified. Fetching camera calibration parameters from Honeycomb based on camera device IDs and time span')
        camera_calibrations = process_pose_data.honeycomb_io.fetch_camera_calibrations(
            camera_ids=camera_device_ids,
            start=start,
            end=end,
            uri=uri,
            token_uri=token_uri,
            audience=audience,
            client_id=client_id,
            client_secret=client_secret
        )
    if coordinate_space_id is None:
        coordinate_space_id = extract_coordinate_space_id_from_camera_calibrations(camera_calibrations)
    if pose_3d_limits is None:
        logger.info('3D pose spatial limits not specified. Generating default spatial limits based on specified room spatial limits and specified pose model')
        pose_3d_limits = generate_pose_3d_limits(
            pose_model_id=pose_model_id,
            room_x_limits=room_x_limits,
            room_y_limits=room_y_limits,
            client=client,
            uri=uri,
            token_uri=token_uri,
            audience=audience,
            client_id=client_id,
            client_secret=client_secret
        )
    pose_reconstruction_3d_metadata = {
        'inference_execution': inference_execution,
        'start': start,
        'end': end,
        'environment_id': environment_id,
        'pose_model_id': pose_model_id,
        'room_x_limits': room_x_limits,
        'room_y_limits': room_y_limits,
        'camera_assignment_ids': camera_assignment_ids,
        'camera_device_id_lookup': camera_device_id_lookup,
        'camera_calibrations': camera_calibrations,
        'coordinate_space_id': coordinate_space_id,
        'poses_2d_json_format': poses_2d_json_format,
        'min_keypoint_quality': min_keypoint_quality,
        'min_num_keypoints': min_num_keypoints,
        'min_pose_quality': min_pose_quality,
        'min_pose_pair_score': min_pose_pair_score,
        'max_pose_pair_score': max_pose_pair_score,
        'pose_pair_score_distance_method': pose_pair_score_distance_method,
        'pose_pair_score_pixel_distance_scale': pose_pair_score_pixel_distance_scale,
        'pose_pair_score_summary_method': pose_pair_score_summary_method,
        'pose_3d_limits': pose_3d_limits,
        'pose_3d_graph_initial_edge_threshold': pose_3d_graph_initial_edge_threshold,
        'pose_3d_graph_max_dispersion': pose_3d_graph_max_dispersion,
        'include_track_labels': include_track_labels
    }
    return pose_reconstruction_3d_metadata

def generate_pose_tracking_3d_metadata(
    start,
    end,
    environment_id,
    pose_reconstruction_3d_inference_id,
    max_match_distance=None,
    max_iterations_since_last_match=None,
    centroid_position_initial_sd=None,
    centroid_velocity_initial_sd=None,
    reference_delta_t_seconds=None,
    reference_velocity_drift=None,
    position_observation_sd=None
):
    logger.info('Generating inference execution object')
    inference_execution = generate_pose_tracking_3d_inference_execution(
        environment_id,
        start,
        end
    )
    pose_tracking_3d_metadata = {
        'inference_execution': inference_execution,
        'start': start,
        'end': end,
        'environment_id': environment_id,
        'pose_reconstruction_3d_inference_id': pose_reconstruction_3d_inference_id,
        'max_match_distance': max_match_distance,
        'max_iterations_since_last_match': max_iterations_since_last_match,
        'centroid_position_initial_sd': centroid_position_initial_sd,
        'centroid_velocity_initial_sd': centroid_velocity_initial_sd,
        'reference_delta_t_seconds': reference_delta_t_seconds,
        'reference_velocity_drift': reference_velocity_drift,
        'position_observation_sd': position_observation_sd
    }
    return pose_tracking_3d_metadata

def generate_pose_track_3d_interpolation_metadata(
    base_dir,
    environment_id,
    pose_tracking_3d_inference_id,
    pose_processing_subdirectory='pose_processing',
    pose_tracks_3d_directory_name='pose_tracks_3d',
    pose_tracking_3d_metadata_filename_stem='pose_tracking_3d_metadata'
):
    logger.info('Generating inference execution object')
    inference_execution = generate_pose_track_3d_interpolation_inference_execution(
        environment_id
    )
    logger.info('Fetching metadata from pose tracking stage')
    pose_tracking_3d_metadata = process_pose_data.read_metadata_local(
        inference_id_local=pose_tracking_3d_inference_id,
        base_dir=base_dir,
        environment_id=environment_id,
        output_subdirectory_name=pose_tracks_3d_directory_name,
        metadata_filename_stem=pose_tracking_3d_metadata_filename_stem,
        pose_processing_subdirectory=pose_processing_subdirectory
    )
    pose_reconstruction_3d_inference_id = pose_tracking_3d_metadata['pose_reconstruction_3d_inference_id']
    pose_track_3d_interpolation_metadata = {
        'inference_execution': inference_execution,
        'environment_id': environment_id,
        'pose_tracking_3d_inference_id': pose_tracking_3d_inference_id,
        'pose_reconstruction_3d_inference_id': pose_reconstruction_3d_inference_id,
    }
    return pose_track_3d_interpolation_metadata

def generate_download_position_data_metadata(
    datapoint_timestamp_min,
    datapoint_timestamp_max,
    start,
    end,
    environment_id
):
    logger.info('Generating inference execution object')
    inference_execution = generate_download_position_data_inference_execution(
        environment_id
    )
    download_position_data_metadata = {
        'inference_execution': inference_execution,
        'datapoint_timestamp_min': datapoint_timestamp_min,
        'datapoint_timestamp_max': datapoint_timestamp_max,
        'start': start,
        'end': end,
        'environment_id': environment_id,
    }
    return download_position_data_metadata

def generate_pose_track_3d_identification_metadata(
    base_dir,
    environment_id,
    pose_track_3d_interpolation_inference_id,
    pose_processing_subdirectory='pose_processing',
    pose_track_3d_interpolation_directory_name='pose_track_3d_interpolation',
    pose_track_3d_interpolation_metadata_filename_stem='pose_track_3d_interpolation_metadata'
):
    logger.info('Generating inference execution object')
    inference_execution = generate_pose_track_3d_identification_inference_execution(
        environment_id
    )
    logger.info('Fetching metadata from pose track interpolation stage')
    pose_track_3d_interpolation_metadata = process_pose_data.read_metadata_local(
        inference_id_local=pose_track_3d_interpolation_inference_id,
        base_dir=base_dir,
        environment_id=environment_id,
        output_subdirectory_name=pose_track_3d_interpolation_directory_name,
        metadata_filename_stem=pose_track_3d_interpolation_metadata_filename_stem,
        pose_processing_subdirectory=pose_processing_subdirectory
    )
    pose_reconstruction_3d_inference_id = pose_track_3d_interpolation_metadata['pose_reconstruction_3d_inference_id']
    pose_tracking_3d_inference_id = pose_track_3d_interpolation_metadata['pose_tracking_3d_inference_id']
    pose_track_3d_interpolation_metadata = {
        'inference_execution': inference_execution,
        'environment_id': environment_id,
        'pose_track_3d_interpolation_inference_id': pose_track_3d_interpolation_inference_id,
        'pose_reconstruction_3d_inference_id': pose_reconstruction_3d_inference_id,
        'pose_tracking_3d_inference_id': pose_tracking_3d_inference_id,
    }
    return pose_track_3d_interpolation_metadata

def generate_pose_reconstruction_3d_inference_execution(
    environment_id,
    start,
    end
):
    inference_id_local = uuid4().hex
    inference_execution_start = datetime.datetime.now(tz=datetime.timezone.utc)
    inference_execution_name = 'Reconstruct 3D poses from 2D poses'
    inference_execution_notes = 'Environment: {} Start: {} End: {}'.format(
        environment_id,
        start.isoformat(),
        end.isoformat()
    )
    inference_execution_model = 'process_pose_data.process.reconstruct_poses_3d_alphapose_local_by_time_segment'
    inference_execution_version = '2.4.0'
    inference_execution = {
        'inference_id_local': inference_id_local,
        'name': inference_execution_name,
        'notes': inference_execution_notes,
        'model': inference_execution_model,
        'version': inference_execution_version,
        'execution_start': inference_execution_start,

    }
    return inference_execution

def generate_pose_tracking_3d_inference_execution(
    environment_id,
    start,
    end,
):
    inference_id_local = uuid4().hex
    inference_execution_start = datetime.datetime.now(tz=datetime.timezone.utc)
    inference_execution_name = 'Build 3D pose tracks from 3D poses'
    inference_execution_notes = 'Environment: {} Start: {} End: {}'.format(
        environment_id,
        start.isoformat(),
        end.isoformat()
    )
    inference_execution_model = 'process_pose_data.process.generate_pose_tracks_3d_local_by_time_segment'
    inference_execution_version = '2.4.0'
    inference_execution = {
        'inference_id_local': inference_id_local,
        'name': inference_execution_name,
        'notes': inference_execution_notes,
        'model': inference_execution_model,
        'version': inference_execution_version,
        'execution_start': inference_execution_start,

    }
    return inference_execution

def generate_pose_track_3d_interpolation_inference_execution(
    environment_id
):
    inference_id_local = uuid4().hex
    inference_execution_start = datetime.datetime.now(tz=datetime.timezone.utc)
    inference_execution_name = 'Interpolate 3D pose tracks'
    inference_execution_notes = 'Environment: {}'.format(
        environment_id
    )
    inference_execution_model = 'process_pose_data.process.interpolate_pose_tracks_3d_local_by_pose_track'
    inference_execution_version = '2.4.0'
    inference_execution = {
        'inference_id_local': inference_id_local,
        'name': inference_execution_name,
        'notes': inference_execution_notes,
        'model': inference_execution_model,
        'version': inference_execution_version,
        'execution_start': inference_execution_start,

    }
    return inference_execution

def generate_download_position_data_inference_execution(
    environment_id
):
    inference_id_local = uuid4().hex
    inference_execution_start = datetime.datetime.now(tz=datetime.timezone.utc)
    inference_execution_name = 'Download UWB position data'
    inference_execution_notes = 'Environment: {}'.format(
        environment_id
    )
    inference_execution_model = 'process_pose_data.process.download_position_data_by_datapoint'
    inference_execution_version = '2.4.0'
    inference_execution = {
        'inference_id_local': inference_id_local,
        'name': inference_execution_name,
        'notes': inference_execution_notes,
        'model': inference_execution_model,
        'version': inference_execution_version,
        'execution_start': inference_execution_start,

    }
    return inference_execution

def generate_pose_track_3d_identification_inference_execution(
    environment_id
):
    inference_id_local = uuid4().hex
    inference_execution_start = datetime.datetime.now(tz=datetime.timezone.utc)
    inference_execution_name = 'Identify 3D pose tracks'
    inference_execution_notes = 'Environment: {}'.format(
        environment_id
    )
    inference_execution_model = 'process_pose_data.process.identify_pose_tracks_3d_local_by_segment'
    inference_execution_version = '2.4.0'
    inference_execution = {
        'inference_id_local': inference_id_local,
        'name': inference_execution_name,
        'notes': inference_execution_notes,
        'model': inference_execution_model,
        'version': inference_execution_version,
        'execution_start': inference_execution_start,

    }
    return inference_execution

def extract_coordinate_space_id_from_camera_calibrations(camera_calibrations):
    coordinate_space_ids = set([camera_calibration.get('space_id') for camera_calibration in camera_calibrations.values()])
    if len(coordinate_space_ids) > 1:
        raise ValueError('Multiple coordinate space IDs found in camera calibration data')
    coordinate_space_id = list(coordinate_space_ids)[0]
    return coordinate_space_id

def generate_pose_3d_limits(
    pose_model_id,
    room_x_limits,
    room_y_limits,
    client=None,
    uri=None,
    token_uri=None,
    audience=None,
    client_id=None,
    client_secret=None
):
    pose_model = process_pose_data.honeycomb_io.fetch_pose_model_by_pose_model_id(
        pose_model_id,
        uri=uri,
        token_uri=token_uri,
        audience=audience,
        client_id=client_id,
        client_secret=client_secret
    )
    pose_model_name = pose_model.get('model_name')
    pose_3d_limits = process_pose_data.analyze.pose_3d_limits_by_pose_model(
        room_x_limits=room_x_limits,
        room_y_limits=room_y_limits,
        pose_model_name=pose_model_name
    )
    return pose_3d_limits
