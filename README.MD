# Bulgarian Electrical Grid Assistant

A Home Assistant integration that monitors the Bulgaria electricity grid websites for power interruption notifications and alerts you when your address will be affected.

> **⚠️ BETA WARNING**: This integration is currently in beta. It may contain bugs or undergo significant changes. Use at your own risk.

## Features

- Daily scraping of power interruption announcements from multiple power companies
- Currently supports:
  - ERP Sever (planned interruptions)
  - ERYug (both planned and unplanned interruptions)
- Monitors multiple addresses (add as many as you need)
- Binary sensor that turns ON when your address is affected
- Detailed sensor showing interruption date, time, and provider
- Compatible with Home Assistant notifications

## Installation

### HACS Installation (Recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance
2. Add this repository as a custom repository in HACS:
   - Go to HACS > Integrations
   - Click the three dots in the top right corner
   - Select "Custom repositories"
   - Add the URL of this repository
   - Select "Integration" as the category
3. Click "Install" on the Bulgarian Electrical Grid Assistant card
4. Restart Home Assistant

### Manual Installation

1. Download the latest release or clone this repository
2. Create a directory structure in your Home Assistant configuration folder:

   ```
   custom_components/bulgarian_electrical_grid_assistant/
   ```

3. Copy all files from this repository into the directory
4. Restart Home Assistant

## Configuration

1. In Home Assistant, go to **Configuration** > **Integrations**
2. Click the "+ Add Integration" button
3. Search for "Bulgarian Electrical Grid Assistant"
4. Enter your configuration:
   - **Addresses**: Enter your street addresses, separated by commas
   - **Scan Interval**: How often to check for updates (minimum 3600 seconds/1 hour)
   - **Providers**: Select which power companies to monitor (ERP and/or ERYug)

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| Addresses | Comma-separated list of your addresses to monitor | Required |
| Scan Interval | Interval in seconds between checks | 86400 (24 hours) |
| Providers | Which power companies to monitor | All providers enabled |

## Usage

After installation, the integration creates two entities:

1. **Binary Sensor**: `binary_sensor.power_interruption_alert`
   - State: ON when a power interruption is scheduled for your address
   - Attributes:
     - `matched_address`: Which of your addresses matched
     - `interruption_date`: Date of the scheduled interruption
     - `interruption_time`: Time of the scheduled interruption
     - `provider`: Which power company reported the interruption
     - `type`: Type of interruption (planned/unplanned)

2. **Sensor**: `sensor.power_interruption_details`
   - State: Shows a summary of the interruption
   - Attributes:
     - `interruption_date`: Date of the scheduled interruption
     - `interruption_time`: Time of the scheduled interruption
     - `affected_addresses`: List of all affected addresses
     - `provider`: Which power company reported the interruption
     - `type`: Type of interruption (planned/unplanned)

## Setting Up Notifications

To receive notifications when a power interruption is scheduled for your address:

1. Go to **Configuration** > **Automations & Scenes**
2. Click the "+ Create Automation" button
3. Add a trigger:
   - Trigger type: State
   - Entity: `binary_sensor.power_interruption_alert`
   - From: `off`
   - To: `on`
4. Add an action:
   - Action type: Call service
   - Service: `notify.mobile_app_your_phone` (replace with your notification service)
   - Service data:

     ```yaml
     title: "Power Interruption Alert!"
     message: "Power interruption scheduled for {{ state_attr('binary_sensor.power_interruption_alert', 'matched_address') }} on {{ state_attr('binary_sensor.power_interruption_alert', 'interruption_date') }} at {{ state_attr('binary_sensor.power_interruption_alert', 'interruption_time') }} by {{ state_attr('binary_sensor.power_interruption_alert', 'provider') }}"
     ```

## Troubleshooting

If the integration isn't working as expected:

- Check Home Assistant logs for errors: **Configuration** > **System** > **Logs**
- Verify your addresses match the format used on the website
- Try adding partial street names if full addresses don't match
- Make sure the integration has internet access
- Check that you've selected the correct providers for your region

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
