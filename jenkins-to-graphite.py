#!/usr/bin/python
#
# Send various statistics about jenkins to graphite
#
# Jeremy Katz <katzj@hubspot.com>
# Copyright 2012, HubSpot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import base64
import logging
import optparse
import sys
import socket
import time
import urllib2
import boto.ec2.cloudwatch
from datetime import date

try:
    # this should be available in any python 2.6 or newer
    import json
except:
    try:
        # simplejson is a good replacement on 2.5 installs
        import simplejson as json
    except:
        print "FATAL ERROR: can't find any json library for python"
        print "Please install simplejson, json, or upgrade to python 2.6+"
        sys.exit(1)


# end json import


class JenkinsServer(object):
    def __init__(self, base_url, user, password):
        self.base_url = base_url
        self.user = user
        self.password = password

        self._opener = None

    @property
    def opener(self):
        """Creates a urllib2 opener with basic auth for talking to jenkins"""
        if self._opener is None:
            opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
            if self.user or self.password:
                opener.addheaders = [
                    (("Authorization", "Basic " + base64.encodestring("%s:%s" % (self.user, self.password))))]
            urllib2.install_opener(opener)
            self._opener = opener

        return self._opener

    def get_raw_data(self, url):
        """Get the data from jenkins at @url and return it as a dictionary"""

        try:
            f = self.opener.open("%s/%s" % (self.base_url, url))
            response = f.read()
            f.close()
            data = json.loads(response)
        except Exception, e:
            logging.warn("Unable to get jenkins response for url %s: %s" % (url, e))
            return {}

        return data

    def get_data(self, url):
        return self.get_raw_data("%s/api/json" % url)


class Debug(object):
    def __init__(self, job, namespace):
        self.job = job.rstrip('.')
        self.namespace = namespace.rstrip('.')

        self.data = {}

    def add_data(self, key, value):
        self.data["%s.%s.%s" % (self.namespace, self.job, key)] = value

    def _data_as_msg(self):
        msg = ""
        now = date.fromtimestamp(time.time())
        for (key, val) in self.data.items():
            msg += "%s %.1f %s\n" % (key, val, now)
        return msg

    def send(self):
        print "DEBUG OUTPUT:"
        print self._data_as_msg()
        return True


class GraphiteServer(object):
    def __init__(self, server, port, job, namespace):
        self.server = server
        self.port = int(port)
        self.job = job.rstrip('.')
        self.namespace = namespace.rstrip('.')

        self.data = {}

    def add_data(self, key, value):
        self.data["%s.%s.%s" % (self.namespace, self.job, key)] = value

    def _data_as_msg(self):
        msg = ""
        now = date.fromtimestamp(time.time())
        for (key, val) in self.data.items():
            msg += "%s %s %s\n" % (key, val, now)
        return msg

    def send(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.server, self.port))
            s.sendall(self._data_as_msg())
            s.close()
        except Exception, e:
            logging.warn("Unable to send msg to graphite: %s" % (e,))
            return False

        return True


class CloudwatchServer(object):
    def __init__(self, region, job, namespace):
        self.job = job.rstrip('.')
        self.namespace = namespace.rstrip('.')
        self.region = region

        self.data = {}

    def add_data(self, key, value):
        self.data["%s.%s.%s" % (self.namespace, self.job, key)] = value

    def _data_as_msg(self):
        msg = ""
        now = date.fromtimestamp(time.time())
        for (key, val) in self.data.items():
            msg += "%s %.1f %s\n" % (key, val, now)
        return msg

    def send(self):
        try:
            now = date.fromtimestamp(time.time())
            cwc = boto.ec2.cloudwatch.connect_to_region(self.region)

            for (key, val) in self.data.items():
                cwc.put_metric_data(namespace=self.namespace, name=key, value=val, timestamp=now, unit="Count")

        except Exception, e:
            logging.warn("Unable to send msg to cloudwatch: %s" % (e,))
            return False

        return True


def parse_args():
    parser = optparse.OptionParser()
    parser.add_option("", "--graphite-server",
                      help="Host name of the server running graphite")
    parser.add_option("", "--graphite-port",
                      default="2003")
    parser.add_option("", "--jenkins-url",
                      help="Base url of your jenkins server (ex http://jenkins.example.com")
    parser.add_option("", "--jenkins-user",
                      help="User to authenticate with for jenkins")
    parser.add_option("", "--jenkins-password",
                      help="Password for authenticating with jenkins")

    parser.add_option("", "--job",
                      help="Job view to monitor for success/failure")
    parser.add_option("", "--namespace", default="Jenkins",
                      help="Used as either the Cloudwatch metric namespace or the Graphite metric namespace")
    parser.add_option("", "--region", default="us-west-2",
                      help="Cloudwatch region where these metrics reside")
    parser.add_option("", "--label", action="append", dest="labels",
                      help="Fetch stats applicable to this node label. Can bee applied multiple times for monitoring more labels.")
    parser.add_option("", "--debug",
                      help="Output the data and do not send to Cloudwatch or Graphite.")

    (opts, args) = parser.parse_args()

    if not opts.debug and not opts.region and not opts.graphite_server:
        print >> sys.stderr, "Need to specify either the target graphite server or cloudwatch region"
        sys.exit(1)

    if not opts.jenkins_url:
        print >> sys.stderr, "Need to specify the jenkins url"
        sys.exit(1)

    if not opts.job:
        print >> sys.stderr, "Need to specify the jenkins job"
        sys.exit(1)

    return opts


def main():
    opts = parse_args()
    jenkins = JenkinsServer(opts.jenkins_url, opts.jenkins_user,
                            opts.jenkins_password)

    task = Debug(opts.job, opts.namespace)

    if opts.graphite_server and not opts.region and not opts.debug:
        task = GraphiteServer(opts.graphite_server, opts.graphite_port,
                              opts.job, opts.namespace)

    if opts.region and not opts.graphite_server and not opts.debug:
        task = CloudwatchServer(opts.region, opts.job, opts.namespace)

    executor_info = jenkins.get_data("computer")
    queue_info = jenkins.get_data("queue")
    build_info_min = jenkins.get_raw_data(
        "view/All/timeline/data?min=%d&max=%d" % ((time.time() - 60) * 1000, time.time() * 1000))
    build_info_hour = jenkins.get_raw_data(
        "view/All/timeline/data?min=%d&max=%d" % ((time.time() - 3600) * 1000, time.time() * 1000))

    task.add_data("queue.size", len(queue_info.get("items", [])))

    task.add_data("builds.started_builds_last_minute", len(build_info_min.get("events", [])))
    task.add_data("builds.started_builds_last_hour", len(build_info_hour.get("events", [])))

    task.add_data("executors.total", executor_info.get("totalExecutors", 0))
    task.add_data("executors.busy", executor_info.get("busyExecutors", 0))
    task.add_data("executors.free",
                  executor_info.get("totalExecutors", 0) -
                  executor_info.get("busyExecutors", 0))

    nodes_total = executor_info.get("computer", [])
    nodes_offline = [j for j in nodes_total if j.get("offline")]
    task.add_data("nodes.total", len(nodes_total))
    task.add_data("nodes.offline", len(nodes_offline))
    task.add_data("nodes.online", len(nodes_total) - len(nodes_offline))

    if opts.labels:
        for label in opts.labels:
            label_info = jenkins.get_data("label/%s" % label)
            task.add_data("labels.%s.jobs.tiedJobs" % label, len(label_info.get("tiedJobs", [])))
            task.add_data("labels.%s.nodes.total" % label, len(label_info.get("nodes", [])))
            task.add_data("labels.%s.executors.total" % label, label_info.get("totalExecutors", 0))
            task.add_data("labels.%s.executors.busy" % label, label_info.get("busyExecutors", 0))
            task.add_data("labels.%s.executors.free" % label,
                          label_info.get("totalExecutors", 0) -
                          label_info.get("busyExecutors", 0))

    if opts.job:
        builds_info = jenkins.get_data("job/%s" % opts.job)
        jobs = builds_info.get("jobs", [])
        ok = [j for j in jobs if j.get("color", 0) == "blue"]
        fail = [j for j in jobs if j.get("color", 0) == "red"]
        warn = [j for j in jobs if j.get("color", 0) == "yellow"]
        task.add_data("jobs.total", len(jobs))
        task.add_data("jobs.ok", len(ok))
        task.add_data("jobs.fail", len(fail))
        task.add_data("jobs.warn", len(warn))

    task.send()


if __name__ == "__main__":
    main()
