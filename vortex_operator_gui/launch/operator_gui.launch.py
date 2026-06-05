import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def launch_setup(context, *args, **kwargs):
    drone = LaunchConfiguration('drone').perform(context)
    namespace = LaunchConfiguration('namespace').perform(context)

    drone_params = os.path.join(
        get_package_share_directory('auv_setup'),
        'config', 'robots', f'{drone}.yaml',
    )

    return [
        Node(
            package='vortex_operator_gui',
            executable='operator_gui',
            name='operator_gui_node',
            namespace=namespace,
            output='screen',
            parameters=[drone_params],
        ),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('drone', default_value='nautilus',
                              description='Robot config in auv_setup/config/robots to load.'),
        DeclareLaunchArgument('namespace', default_value='nautilus',
                              description='Namespace the robot runs under.'),
        OpaqueFunction(function=launch_setup),
    ])
