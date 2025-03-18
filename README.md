# Home Assistant integratione for Tado Auto-Assist
### Introduction
This integration allows you to use Tado's API to create your own "Auto-Assist". The integration will periodically contact Tado's servers to know the status of the home and will eventually change it upon user indication. 
The operation is based on the use of the [PyTado](https://github.com/chrism0dwk/PyTado) library which will be installed together with the integration.

### Features
- Get the operating mode (Home or Away);
- Get if any open windows have been detected in any area of ​​the home;
- Control of the operating mode (Home or Away) based on georeferencing;
- Suspension of heating in areas of the home where open windows are detected;
- Know the number of mobile devices (associated with the Tado account) in the home. This information is provided as an attribute;
- Know the zones where an open window is detected. This information is provided as an attribute but only if heating suspension is disabled;
- Ability to manage multiple accounts;

### Installation
**Method 1**
1. Install [HACS](https://www.hacs.xyz/);
2. Add a custom repository: on HACS click on 3 dots (top-right corner), then select "custom repository" and add this repository;
3. Search "Tado Assist" on HACS and install it;

**Method 2**
1. Download and copy custom_components/tado_assist folder to custom_components folder in your Home Assistant config folder;

### Preview
Integration controls and sensors:

<img src="/assets/images/preview_service.png" width="300">

Integration config:

<img src="/assets/images/preview_config.png" width="400">
