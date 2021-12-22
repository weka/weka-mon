# weka-mon
Weka Cluster Monitoring


A solution that implements Grafana dashboards with Prometheus, and includes Grafana/Loki for logs and Prometheus/Alertmanager for alerting, with data exporter(s) for Weka.

# Use Overview:  

To use this, do the following:

o Clone this repository

o Run the install.sh

o Edit the export.yml - put your weka server hostnames under hosts: (about line 15). You might also need to set the auth-token.json filename or location.

o Edit the alertmanager configuration file in etc_alertmanager/ (if you're using alertmanager)

o Start with `docker-compose up -d`


Compose will start Grafana, Prometheus, Loki, Alertmanager, and Weka Exporter containers such that all can communicate with each other.

# Data Flow:

The Weka Exporter (export) gathers data from the Weka cluster(s) and presents it such that Prometheus can scrape data from it, and pushes Events to Loki; 
Prometheus gathers data from the Exporter, and forward Alerts to Alertmanager.
Grafana queries Prometheus and Loki for performance metrics, logs, and alerts and displays them.

# Installation:

Clone this repository with 
```
git clone <repo>
```

Run the "install.sh" script to set the permissions on the subdirectories used to persist data between container restarts - this preserves the Grafana, Prometheus and Loki databases.

Edit the configuration as needed.  Start copying etc_alertmanager/alertmanager.yml.sanitized to etc_alertmanager/alertmanager.yml, and edit it to send the alerts to your desired destination (PagerDuty, Slack, Email, Text message - please refer to Prometheus Alertmanager documentation for details if you are unfamiliar with configuring Alertmanager).  Skip this step if you don't want Alerts sent via Alertmanager.

Then run Docker Compose to start the containers:
```
docker-compose up -d
```

Compose will pull the needed containers from docker hub automatically.  For details on the export.yml file, please see https://github.com/weka/export

Grafana Dashboards are automatically provisioned, and Grafana, Loki, Prometheus, and Alertmanager are pre-configured from the config files in the included subdirectories.

# Use

Using a standard web browser, go to http://<this server>:3000 to access the Grafana Dashboards.

