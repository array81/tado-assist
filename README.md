# Home Assistant integratione for Tado Auto-Assist
### Introduction
This integration allows you to use Tado's API to create your own "Auto-Assist". The integration will periodically contact Tado's servers to know the status of the home and will eventually change it upon user indication.

### Features
- Get the operating mode (Home or Away);
- Get if any open windows have been detected in any area of ​​the home;
- Control of the operating mode (Home or Away) based on georeferencing;
- Suspension of heating in areas of the home where open windows are detected;
- Know the number of mobile devices (associated with the Tado account) in the home. This information is provided as an attribute;
- Know the zones where an open window is detected. This information is provided as an attribute but only if heating suspension is disabled;
- Ability to manage multiple accounts;

### Preview
Integration controls and sensors:

<img src="/assets/images/preview_service.png" width="300">

Integration config:

<img src="/assets/images/preview_config.png" width="400">
