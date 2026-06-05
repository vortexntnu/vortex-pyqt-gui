import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'vortex_operator_gui'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='jorgen',
    maintainer_email='jorgen.fjermedal@hotmail.com',
    description='Simple PyQt5 operator interface for the Vortex AUV.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'operator_gui = vortex_operator_gui.main:main',
        ],
    },
)
