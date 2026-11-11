#!/bin/bash
# Lock camera settings for LeRobot recording. Run before each session.
for cam in /dev/cam_gripper /dev/cam_scene; do
  v4l2-ctl -d $cam -c focus_automatic_continuous=0 -c auto_exposure=1 -c white_balance_automatic=0
done
v4l2-ctl -d /dev/cam_gripper -c focus_absolute=68 -c exposure_time_absolute=166 -c white_balance_temperature=4600
v4l2-ctl -d /dev/cam_scene -c focus_absolute=40 -c exposure_time_absolute=83 -c white_balance_temperature=3294
