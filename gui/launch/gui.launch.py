# gui.launch.py
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import SetEnvironmentVariable

def generate_launch_description():
    return LaunchDescription([
        SetEnvironmentVariable("QT_QPA_PLATFORM", "xcb"),
        SetEnvironmentVariable("XDG_SESSION_TYPE", "x11"),
        Node(
            package="gui",
            executable="gui",
            name="gui",
            output="screen",
        ),
    ])
