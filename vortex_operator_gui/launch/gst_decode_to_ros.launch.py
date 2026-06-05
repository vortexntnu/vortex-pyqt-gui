from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

SENSORS = [
    {
        'name': 'front_camera',
        'port': 5000,
        'output_format': 'BGR',
        'output_topic': '/gst_decoded/front_camera/image_raw',
    },
    {
        'name': 'down_camera',
        'port': 5001,
        'output_format': 'BGR',
        'output_topic': '/gst_decoded/down_camera/image_raw',
    },
    {
        'name': 'sonar',
        'port': 5002,
        'output_format': 'GRAY8',
        'output_topic': '/gst_decoded/sonar/image_raw',
    },
]


def _launch_setup(context, *args, **kwargs):
    hw = LaunchConfiguration('hw').perform(context).lower() == 'true'

    return [
        Node(
            package='gstreamer_to_ros',
            executable='gstreamer_to_ros_node',
            name=f'decoder_{s["name"]}',
            parameters=[{
                'host': '0.0.0.0',
                'port': s['port'],
                'output_topic': s['output_topic'],
                'output_format': s['output_format'],
                'hw_decoder': hw,
            }],
            output='screen',
        )
        for s in SENSORS
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'hw',
            default_value='false',
            description='Use NVIDIA hardware H.265 decoder (nvh265dec). '
                        'Set true if an NVIDIA GPU is available.',
        ),
        OpaqueFunction(function=_launch_setup),
    ])
