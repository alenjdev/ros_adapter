#!/usr/bin/env python3

import json
import os
from multiprocessing import Lock
from typing import Dict, List

import rospy
import rostopic
import rosnode
from formant.sdk.agent.v1 import Client as FormantClient

from ros_topic_stats import RosTopicStats


class RosDiagnosticsCollector:
    rosnode.get_node_names()

    def __init__(self):
        rospy.init_node("ros_diagnostics_collector")
        self._stream_name = os.getenv("STREAM_NAME", "ros_diagnostics")
        agent_url = os.getenv(
            "AGENT_URL", "unix: // /var/lib/formant/agent.sock")

        self._r = rostopic.ROSTopicHz(-1)
        self._fclient = FormantClient(
            agent_url=agent_url, ignore_throttled=True)
        self._subscribers = {}  # type: Dict[str,rospy.Subscriber]
        self._topic_stats = []  # type: List[RosTopicStats]
        self._online_nodes = []  # type: List[str]
        self._lock = Lock()
        self._refresh_topics()
        self._lookup_timer = rospy.Timer(
            rospy.Duration(0.2), self._lookup_and_post)
        self._refresh_timer = rospy.Timer(
            rospy.Duration(10), self._refresh_topics)
        rospy.spin()

    def _refresh_topics(self, event=None):
        self._lock.acquire()
        remaining_topics = list(self._subscribers.keys())
        pubs_out, _ = rostopic.get_topic_list()
        for topic_tuple in pubs_out:
            topic_name = topic_tuple[0]
            if topic_name in remaining_topics:
                remaining_topics.remove(topic_name)
                continue
            topic_type = topic_tuple[1]
            self._topic_stats.append(RosTopicStats(topic_name, topic_type))
            self._subscribers[topic_name] = rospy.Subscriber(
                topic_name, rospy.AnyMsg, self._r.callback_hz, callback_args=topic_name,
            )

        for topic in remaining_topics:
            self._subscribers[topic].unregister()
            del self._subscribers[topic]
            self._topic_stats = [
                stat for stat in self._topic_stats if stat.name != topic]
        rospy.sleep(1)
        self._lock.release()
