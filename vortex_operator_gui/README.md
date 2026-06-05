# vortex_operator_gui

A simple PyQt5 operator interface for the Vortex AUV. Separate from the older
`vortex_pyqt_gui` package.

## Features
- Live **operation mode** and **killswitch** display (polled at 1 Hz via
  `get_operation_mode`).
- Setters: operation mode (`AUTONOMOUS` / `MANUAL` / `REFERENCE`) and killswitch
  (engage / release).
- Mission controls: **Start mission**, **Reset origin**, and **Wipe**
  (publishes an empty message on `mission/wipe`).
- **Waypoint sender** (one waypoint at a time) using the `WaypointManager`
  action. Position (m) and orientation (deg) inputs; selecting a waypoint mode
  from the dropdown greys out the fields that mode doesn't use; ticking **Keep
  altitude** greys the Z/depth field and enables the desired altitude field.
  Sending a new goal always cancels the current one. A **Cancel current** button
  stops the active goal; live tracking feedback shows on the status line.
- Status line + scrolling log of all command results.

## Build & run
```bash
cd ~/ros2_ws
colcon build --packages-select vortex_operator_gui
source install/setup.bash
ros2 launch vortex_operator_gui operator_gui.launch.py            # nautilus
ros2 launch vortex_operator_gui operator_gui.launch.py drone:=orca namespace:=orca
```
Or directly: `ros2 run vortex_operator_gui operator_gui` (uses default names,
no namespace).

## Configuration
Topic / service / action names are read from the robot config in
`auv_setup/config/robots/<drone>.yaml` (e.g. `nautilus.yaml`), loaded by the
launch file. The node runs inside the robot namespace, so the relative names
resolve to `/<namespace>/<name>`. To change an endpoint, edit the robot yaml —
not this package. Launch args: `drone` (which robot yaml) and `namespace`.

### Assumptions to verify
- `start_mission` and `reset_origin` are typed as **`std_srvs/Trigger`** (their
  `.srv` definitions weren't found in the workspace). If they differ, update the
  client types in `vortex_operator_gui/ros_interface.py`.
- The per-mode field mapping in `main_window.py` (`MODE_FIELDS`) is a best guess
  at each `WaypointMode`'s semantics — adjust to match the controller.
