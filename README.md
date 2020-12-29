# weka-mon
Weka Cluster Monitoring


A solution that implements Grafana dashboards with Prometheus, and includes Grafana/Loki for logs and Prometheus/Alertmanager for alerting.

# Use Overview:  

Clone this repository, edit the alertmanager configuration file, start with docker-compose.   Compose will start Grafana, Prometheus, Loki, Alertmanager, and Weka Exporter containers such that all can communicate with each other.

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

Set and export the CLUSTER_SPEC environment variable so this software can communicate with the cluster(s).  See CLUSTER_SPEC section below.

Then run Docker Compose to start the containers:
```
docker-compose up -d
```

Compose will pull the needed containers from docker hub automatically.  You can optionally build the ```export``` container yourself from the included sources (see the ```export``` subdirectory README.md for details.

Grafana Dashboards are automatically provisioned, and Grafana, Loki, Prometheus, and Alertmanager are pre-configured from the config files in the included subdirectories.

# Use

Using a standard web browser, go to http://<this server>:3000 to access the Grafana Dashboards.

# CLUSTER_SPEC

The CLUSTER_SPEC environment variable is used to set where the Weka clusters the Exporter (```export```) will pull data from.

The format of a cluster specification is similar to that used by the Stateless Clients: a list of weka backend servers, plus the addition of optional authentication parameters.

Generally, the format is as such:
```
<wekaserver1>,<wekaserver2>,...,<wekaserverN>:authfile
```

Multiple clusters can be monitored by listing the cluster spec for each cluster.  For example:
```
export CLUSTER_SPEC="weka1,weka2,weka5:~/.weka/cluster1_auth tweka1,tweka4,tweka7:~/.weka/cluster2_auth"
```

The auth files can be generated with the ```weka user login``` command.  See docs.weka.io for details.   If you are using the default user/password (not suggested), you can leave off the ```:authfile``` and it will use the default credentials automatically.  ie: ```export CLUSTER_SPEC="weka1,weka2,weka5"```


