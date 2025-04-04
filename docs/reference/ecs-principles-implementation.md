---
mapped_pages:
  - https://www.elastic.co/guide/en/ecs/current/ecs-principles-implementation.html
applies_to:
  stack: all
  serverless: all
---

# Implementation patterns [ecs-principles-implementation]

Normalizing data provides a more consistent view of events from various data sources. Following these conventions will help to better describe, discover, identify, and categorize events.


## Base fields [_base_fields]

The group of individual fields residing outside any field set at the top-level of ECS are known as base fields.

ECS events follow these conventions with the base fields:

@timestamp
:   All events must populate [`@timestamp`](/reference/ecs-base.md#field-timestamp) with the event’s original timestamp.

message
:   Most events should populate [`message`](/reference/ecs-base.md#field-message).

ecs.version
:   The referenced [`ecs.version`](/reference/ecs-ecs.md#field-ecs-version) used to develop the data mapping or ingest pipeline. This value helps detect when mappings update or fall behind. It can also help explain why a particular data source isn’t populating the same fields as another.

tags and labels
:   The [`tags`](/reference/ecs-base.md#field-tags) and [`labels`](/reference/ecs-base.md#field-labels) fields add simple metadata as `keyword` values.


## Host [_host]

In ECS, the `host` is the computing instance where the event happened. A `host` can be a physical device, virtual machine, container, or cloud instance.

The [`host.*`](/reference/ecs-host.md) field set contains common attributes for different computing instances. Certain host types have more fields to capture specific details, like `cloud.*` or `container.*`.


## Agent and observer [_agent_and_observer]

An agent is software that collects, observes, measures, or detects the event. The [`agent.*`](/reference/ecs-agent.md) fields capture details about which agent entity captured the event, including the agent’s version. Examples of agents are Beats and Elastic Agent.

An `observer` is an external monitoring or intermediary device, like a firewall, APM server, or web proxy. These devices monitor and detect network, security, application events. Capture the details for these device types in the [`observer.*`](/reference/ecs-observer.md) field set.


## Timestamps [_timestamps]

ECS requires the `@timestamp` field on every event. Some events also contain extra timestamps to capture.

@timestamp
:   All events must populate [`@timestamp`](/reference/ecs-base.md#field-timestamp) with when the event originated.

event.created
:   The timestamp of when an agent or pipeline saw the event.

event.ingested
:   The timestamp of when an event arrived in the central data store, like Elasticsearch.

These three timestamps should typically follow a chronological order:

```sh
@timestamp < event.created < event.ingested
```

event.start
:   This timestamp marks the beginning of the event activity. For example, in a network session, [`event.start`](/reference/ecs-event.md#field-event-start) is the timestamp of the first observed packet in the flow.

event.end
:   This timestamp marks the end of the activity. In a network flow, [`event.end`](/reference/ecs-event.md#field-event-end) is the timestamp of the last observed packet in the flow.

event.duration
:   The difference of `event.end` and `event.start`:

```sh
event.duration = event.end - event.start
```


## Origin [_origin]

Specific `event.*` fields exist to capture where an event originated.

event.provider
:   Contains the name of the software or operating subsystem that generated the event.

event.module
:   If the ingest agent or pipeline has a concept of modules or plugins, populate [`event.module`](/reference/ecs-event.md#field-event-module) with the module or plugin name.

event.dataset
:   Used to define different types of logs or metrics from an event source. The recommended convention is `<moduleName>.<datasetName>`. For Apache web server access logs, the [`event.dataset`](/reference/ecs-event.md#field-event-dataset) value will be `apache.access`.


## Categorization [_categorization]

The event categorization fields group similar events using allowed values for four fields:

* `event.kind`
* `event.category`
* `event.type`
* `event.outcome`

[Using the Categorization Fields](/reference/ecs-using-categorization-fields.md) covers more details on using these four fields together to categorize events.


## Enriching events [_enriching_events]

A monitoring agent or ingest pipeline can add more details to the original event. ECS has many fields to hold these enrichment details.


## Lookups [_lookups]

GeoIP
:   Add information about the geographical location of an IPv4 or IPv6 address. Often used to populate the `geo.*` fields nested under network transaction fields like `source.*`, `destination.*`, `client.*`, and `server.*`.

```json
{
  "source": {
    "address": "8.8.8.8",
    "ip": "8.8.8.8",
    "geo": {
      "continent_name": "North America",
      "country_name": "United States",
      "country_iso_code": "US",
      "location": { "lat": 37.751, "lon": -97.822 }
    }
  }
}
```

Autonomous system number
:   Autonomous System Number (ASN) database lookups determine the ASN associated with an IP address.


## Parsing [_parsing]

User-agent
:   Break the user-agent into individual fields.

```json
{
  "user_agent": {
    "user_agent": {
      "name": "Chrome",
      "original": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36",
      "version": "51.0.2704.103",
      "os": {
        "name": "Mac OS X",
        "version": "10.10.5",
        "full": "Mac OS X 10.10.5",
        "platform": "darwin",
        "type": "macos"
      },
      "device" : {
        "name" : "Mac"
      }
    }
  }
}
```

URL
:   A URL can also break down into its discrete parts.

```json
{
  "original" : "http://myusername:mypassword@www.example.com:80/foo.gif?key1=val1&key2=val2#fragment",
  "url" : {
    "path" : "/foo.gif",
    "fragment" : "fragment",
    "extension" : "gif",
    "password" : "mypassword",
    "original" : "http://myusername:mypassword@www.example.com:80/foo.gif?key1=val1&key2=val2#fragment",
    "scheme" : "http",
    "port" : 80,
    "user_info" : "myusername:mypassword",
    "domain" : "www.example.com",
    "query" : "key1=val1&key2=val2",
    "username" : "myusername"
  }
}
```

Domain names
:   Extract the registered domain (also known as the effective top-level domain plus one), sub-domain, and effective top-level domain from a fully-qualified domain name (FQDN).

```json
{
  "fqdn": "www.example.ac.uk",
  "url": {
    "subdomain": "www",
    "registered_domain": "example.ac.uk",
    "top_level_domain": "ac.uk",
    "domain": "www.example.ac.uk"
}
```


## Related fields [_related_fields]

Many events have similar content populating different fields: IP addresses, file hashes, hostnames. Pivot between these events using the [`related.*`](/reference/ecs-related.md) fields.

For example, IP addresses found under the `host.*`, `source.*`, `destination.*`, `client.*`, and `server.*` fields sets and the `network.forwarded_ip` field. By adding all IP addresses in an event to the `related.ip` field, there is now a single field to search for a given IP regardless of what field it appeared:

```sh
related.ip: ["10.42.42.42"]
```

