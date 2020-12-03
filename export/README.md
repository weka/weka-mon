# Weka Metrics Exporter

Version 3.5.0:

Added much more error checking and more complete logging.  Changed Docker image to run unprivledged in the container.  Added --version to weka-metrics-exporter so you can see what version you're running.

All-new Version 3

Metrics exporter for WekaFS. Gathers metrics and statistics from Weka Clusters and exposes a metrics endpoint for Prometheus to scrape.

## What's new

Largely re-written and modularized.   
Now using the weka api to talk to the cluster(s), rather than spawning weka commands.     
Improved logging and new verbosity levels.    
It can now gather metrics from multiple clusters     
Changed command-line arguments, particularly cluster specification (see below - removed -H option)     

## Installation

The simplest installation is to get the docker container via `docker pull weka-solutions/weka-metrics-exporter:latest`

This package should be combined with our Grafana panel, available at `https://github.com/weka/grafana-dashboards`  Follow the instructions there for simple installation.

To run outside a container:
1. Unpack tarball from Releases or clone repository.
2. Make sure you have Python 3.5+ and `pip` installed on your machine.
3. Install package dependencies: `pip install -r requirements.txt`.

## Running the pre-built Docker Container

The pre-built container is now maintained on Docker Hub.  To download it, please run:

```docker pull wekasolutions/metrics-exporter:latest```

If you download the pre-built docker container from this github repository, it may be loaded with:

```docker load metrics-exporter.tar```

Then run with the usual Docker Run command. (see below)

## Docker Run Commands

There are a variety of options when running the conatiner.

To ensure that the container has access to DNS, use the ```--network=host``` directive.  Alternatively it can be run with the -p parameter

If you do not use the ```--network=host```, then you might want to map /etc/hosts into the container with: ```--mount type=bind,source=/etc/hosts,target=/etc/hosts``` so hostnames in the cluster are resolved to ip addresses via /etc/hosts.

If you have changed the default password on the cluster, you will need to pass authentication tokens to the container with ```--mount type=bind,source=/root/.weka/,target=/weka/.weka/```.  Use the ```weka user login ``` command to generate the tokens, which by default are stored in ```~/.weka/```

To have messages logged via syslog on the docker host, use ```--mount type=bind,source=/dev/log,target=/dev/log```  On most hosts, these messages will appear in ```/var/log/messages``` 

If you would like to change the metrics gathered, you can modify the weka-metrics-exporter.yml configuration file, then map that into the container with ```--mount type=bind,source=$PWD/weka-metrics-exporter.yml,target=/weka/weka-metrics-exporter.yml```

Clusters are specified as a list of hostnames or ip addresses, with an optional authfile (see above) like so: ```<wekahost>,<wekahost>,<wekahost>:authfile```, with the minimum being a single wekahost.

You may specify as many clusters to monitor as you wish - just list them on the command line (space-separated).  ``<wekahost>,<wekahost>,<wekahost>:authfile <wekahost>,<wekahost>,<wekahost>:authfile <wekahost>,<wekahost>,<wekahost>:authfile```

For example:

```
docker run -d --network=host \
  --mount type=bind,source=/root/.weka/,target=/weka/.weka/ \
  --mount type=bind,source=/dev/log,target=/dev/log \
  --mount type=bind,source=/etc/hosts,target=/etc/hosts \
  --mount type=bind,source=$PWD/weka-metrics-exporter.yml,target=/weka/weka-metrics-exporter.yml \
  wekasolutions/metrics-exporter -vv -a weka01, weka02,weka09:~/.weka/myauthfile
```

## Metrics Exported

1. Edit the weka-metrics-exporter.yml file. All the metrics that can be collected are defined there. Note that the default contents are sufficient to populate the example dashboards. **Add ONLY what you need**. It does generate load on the cluster to collects these stats.
2. Uncomment any metrics you would like to gather that are commented out. Restart the exporter to start gathering those metrics.
3. To display new metrics in Grafana, add new panel(s) and query. Try to curl the data from the metrics endpoint.



## Manual Configuratrion

Configure prometheus to pull data from the Weka metrics exporter (see prometheus docs). Example Prometheus configuration:

```
# Weka
- job_name: 'weka'
  scrape_interval: 60s
  static_configs:
    - targets: ['localhost:8001']
```

*Important*: Weka clusters update their performance stats once per minute, so setting Prometheus to scrape more often than every 60s is not useful.

It is recommended to be run as a daemon: `nohup ./weka-metrics-exporter -a <target host> &`. or better, run as a system service.

## Configuration

- Use the `-a` option to load-balance the data collection over all the Weka backends.
- `-p` port sets the port number - Default port is 8001
- `-h` will print the help message.

## Docker build instructions (optional)

To build this repositiory:

```
git clone <this repo>
docker build --tag wekasolutions/metrics-exporter .
```
or
```docker build --tag wekasolutions/metrics-exporter https://github.com/weka/weka-metrics-exporter.git```

To save and/or load the image
```
docker save -o metrics-exporter.tar wekasolutions/metrics-exporter
docker load -i  metrics-exporter.tar
```
Comments, issues, etc can be reported in the repository's issues.

Note: This is provided via the GPLv3 license agreement (text in LICENSE.md).  Using/copying this code implies you accept the agreement.

Maintained by vince@weka.io
