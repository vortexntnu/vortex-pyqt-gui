import os
import yaml
from ament_index_python.packages import get_package_share_directory


def load_config() -> dict:
    share_dir = get_package_share_directory("gui")
    config_path = os.path.join(share_dir, "config", "gui_config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


CONFIG = load_config()

WAYPOINT_LAUNCH = CONFIG["drone"]["waypoint_launch"]
ROS_NODE_LAUNCH = CONFIG["ros_node"]["script"]
START_FSM = CONFIG["drone"]["start_fsm"]
CAMERA_FRONT = CONFIG["camera"]["front_camera"]
CAMERA_BOTTOM = CONFIG["camera"]["bottom_camera"]
SSH_HOST = CONFIG["drone"]["ssh_host"]
SSH_KEY = CONFIG["drone"]["ssh_key"]
PIPELINE_DESCRIPTION = CONFIG["camera"]["pipeline_description"]

