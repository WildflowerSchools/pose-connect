
# Shared defaults
PROGRESS_BAR = False
NOTEBOOK = False
FRAMES_PER_SECOND = 10

# 3D pose reconstruction defaults
RECONSTRUCTION_MIN_KEYPOINT_QUALITY = None
RECONSTRUCTION_MIN_NUM_KEYPOINTS = None
RECONSTRUCTION_MIN_POSE_QUALITY = None
RECONSTRUCTION_MIN_POSE_PAIR_SCORE = None
RECONSTRUCTION_MAX_POSE_PAIR_SCORE = 25.0
RECONSTRUCTION_POSE_PAIR_SCORE_DISTANCE_METHOD = 'pixels'
RECONSTRUCTION_POSE_PAIR_SCORE_PIXEL_DISTANCE_SCALE = 5.0
RECONSTRUCTION_POSE_PAIR_SCORE_SUMMARY_METHOD = 'rms'
RECONSTRUCTION_POSE_3D_GRAPH_INITIAL_EDGE_THRESHOLD = 2
RECONSTRUCTION_POSE_3D_GRAPH_MAX_DISPERSION = 0.20
RECONSTRUCTION_INCLUDE_TRACK_LABELS = False
POSE_2D_ID_COLUMN_NAME = 'pose_2d_id'
POSE_2D_IDS_COLUMN_NAME = 'pose_2d_ids'

# 3D pose spatial limit defaults
POSE_3D_FLOOR_Z = 0.0
POSE_3D_FOOT_Z_LIMITS = (0.0, 1.0)
POSE_3D_KNEE_Z_LIMITS = (0.0, 1.0)
POSE_3D_HIP_Z_LIMITS = (0.0, 1.5)
POSE_3D_THORAX_Z_LIMITS = (0.0, 1.7)
POSE_3D_SHOULDER_Z_LIMITS = (0.0, 1.9)
POSE_3D_ELBOW_Z_LIMITS = (0.0, 2.0)
POSE_3D_HAND_Z_LIMITS = (0.0, 3.0)
POSE_3D_NECK_Z_LIMITS = (0.0, 1.9)
POSE_3D_HEAD_Z_LIMITS = (0.0,2.0)
POSE_3D_LIMITS_TOLERANCE = 0.2

# Single timestamp 3D pose reconstruction defaults
RECONSTRUCTION_VALIDATE = False
RECONSTRUCTION_RETURN_DIAGNOSTICS = False

# 3D pose tracking defaults
TRACKING_MAX_MATCH_DISTANCE = 1.0
TRACKING_MAX_ITERATIONS_SINCE_LAST_MATCH = 20
TRACKING_CENTROID_POSITION_INITIAL_SD = 1.0
TRACKING_CENTROID_VELOCITY_INITIAL_SD = 1.0
TRACKING_REFERENCE_DELTA_T_SECONDS = 1.0
TRACKING_REFERENCE_VELOCITY_DRIFT = 0.30
TRACKING_POSITION_OBSERVATION_SD = 0.5
TRACKING_NUM_POSES_PER_TRACK_MIN = 11
POSE_3D_ID_COLUMN_NAME = 'pose_3d_id'
POSE_TRACK_3D_ID_COLUMN_NAME = 'pose_track_3d_id'

# 3D pose track identification defaults
IDENTIFICATION_ID_FIELD_NAMES = ['person_id']
IDENTIFICATION_INTERPOLATION_FIELD_NAMES = ['x_position', 'y_position', 'z_position']
IDENTIFICATION_TIMESTAMP_FIELD_NAME = 'timestamp'
IDENTIFICATION_SENSOR_POSITION_KEYPOINT_INDEX = None
IDENTIFICATION_ACTIVE_PERSON_IDS = None
IDENTIFICATION_IGNORE_Z = True
IDENTIFICATION_MAX_DISTANCE = 2.0
IDENTIFICATION_RETURN_MATCH_STATISTICS=False
IDENTIFICATION_MIN_TRACK_FRACTION_MATCHED = 0.5
