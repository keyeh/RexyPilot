# RexyPilot 🦖

RexyPilot is my personal fork of the OpenPilot driver assistance system with enhancements to reduce distractions and noise. Based on sunnypilot, it enables a distraction-free screen-off driving experience, allowing drivers to use the instrument cluster instead, thanks to improved integration with Toyota and Lexus vehicles.

**Enhancements:**

- Screen stays off while driving, unless critical alerts happen or experimental mode is toggled.
- Improved integration with Toyota and Lexus instrument clusters:
  - LTA icon indicates lateral control engagement status
- Allow distance button toggles regardless of longitudinal control active
- Pause instead of disable lateral control on wrongGear
- Removed annoyances and distractions:
  - Personality change message
  - "Reverse Gear" message
  - Startup message.
  - Pre driver distracted message
  - Lane change messages
  - "Gear not D" message

## Installation

Enter the following URL at installation where you choose "Custom Software".

```
URL not available at the moment. Open an issue on Github for installation instructions
```

## What is openpilot?

[openpilot](http://github.com/commaai/openpilot) is an open source driver assistance system. Currently, openpilot performs the functions of Adaptive Cruise Control (ACC), Automated Lane Centering (ALC), Forward Collision Warning (FCW), and Lane Departure Warning (LDW) for a growing variety of [supported car makes, models, and model years](docs/CARS.md). In addition, while openpilot is engaged, a camera-based Driver Monitoring (DM) feature alerts distracted and asleep drivers. See more about [the vehicle integration](docs/INTEGRATION.md) and [limitations](docs/LIMITATIONS.md).

## What is sunnypilot? 🌞

sunnypilot is a fork of comma.ai's openpilot, an open source driver assistance system. sunnypilot offers the user a unique driving experience for over 300+ supported car makes and models with modified behaviors of driving assist engagements. sunnypilot complies with comma.ai's safety rules as accurately as possible.
