Finalize the Network Manager implementation specification with these decisions: Linux agent networking: routes; Router infrastructure: ubiquiti; Initial device management scope: clients. Include database schema, API contracts, agent protocol, UI pages, deployment configuration, and a complete implementation task file for a coding agent.

Ubiquiti Network Manager
Final implementation specification — Version 1.0

Approved architecture
airOS 8
30–100 devices
Multi-subnet
The decisions are now incorporated into the design:

Decision

Final selection

Network agent

Linux

Network topology

Multiple routed subnets

Router infrastructure

Ubiquiti

Radio firmware

airOS 8

Device coverage

LiteAP GPS and Loco 5AC

Initial priority

Connected client management

Central backend

FastAPI

Frontend

Next.js + TypeScript

Database

PostgreSQL

Deployment

Ubuntu, no Docker

Project name: AirManager (working name: Ubiquiti Network Manager).

1. Important architectural adjustment
Because your Linux agent has routed access to multiple subnets, we should not make UDP broadcast discovery the primary discovery mechanism.

A broadcast from one subnet will not normally cross a router.

Instead, the application will use a hybrid discovery engine:

Configured subnet scanning to find management interfaces.

HTTPS/API probing to identify Ubiquiti radios.

MAC-based identification from the device's own management information.

Optional router-assisted discovery through Ubiquiti router integrations.

Periodic polling of previously registered devices.

Revised discovery architecture

Linux Network Agent

Central discovery and monitoring process

Subnet scanner

Configured CIDRs

Router integration

Optional DHCP / ARP data

airOS identification

Authenticate · Read model · Read MAC · Validate device

Permanent device registry

MAC identity · Current IP · Historical IPs

This approach is more appropriate for your topology and avoids depending on broadcast forwarding.

Important limitation: Scanning a subnet discovers devices that are reachable at their current IP addresses. If a radio changes IP and is no longer in the configured range, the system needs another source of its new address, such as DHCP lease information, router neighbor information, or a configured additional discovery range. Router integration will therefore be an important optional enhancement, not something to assume is automatically available on every Ubiquiti gateway.

I attempted to generate the downloadable Markdown implementation specification, but the file-generation tool is temporarily unavailable. I can't provide a verified download link right now.

The architecture and implementation decisions are established above. The specification is intended to include the database schema, REST API contracts, agent communication protocol, UI requirements, security, Ubuntu deployment configuration, testing criteria, and phased coding-agent instructions.