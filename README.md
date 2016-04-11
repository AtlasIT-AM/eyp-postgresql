# postgresql

![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)

**AtlasIT-AM/eyp-postgresql**: [![Build Status](https://travis-ci.org/AtlasIT-AM/eyp-postgresql.png?branch=master)](https://travis-ci.org/AtlasIT-AM/eyp-postgresql)

#### Table of Contents

1. [Overview](#overview)
2. [Module Description](#module-description)
3. [Setup](#setup)
    * [What postgresql affects](#what-postgresql-affects)
    * [Setup requirements](#setup-requirements)
    * [Beginning with postgresql](#beginning-with-postgresql)
4. [Usage](#usage)
5. [Reference](#reference)
5. [Limitations](#limitations)
6. [Development](#development)
    * [Contributing](#contributing)

## Overview

manages postgresql:
* standalone
* streaming replication

## Module Description

Installs and configures PostgreSQL on CentOS 6

## Setup

### What postgresql affects

* Installs PostgreSQL:
* configures:
  * postgres.conf
  * pg_hba
* it can manage the following DB objects:
  * roles
  * schemas

### Setup Requirements

This module requires pluginsync enabled and **optionally** *eyp/sysctl* module
installed

### Beginning with postgresql

Right now, it only supports PostgreSQL 9.2

## Usage

```puppet
node 'pgm'
{
	#.29

	class { 'sysctl': }

	class { 'postgresql':
		wal_level => 'hot_standby',
		max_wal_senders => '3',
		checkpoint_segments => '8',
		wal_keep_segments => '8',
	}

	postgresql::hba_rule { 'test':
		user => 'replicator',
		database => 'replication',
		address => '192.168.56.0/24',
	}

	postgresql::role { 'replicator':
		replication => true,
		password => 'replicatorpassword',
	}

	postgresql::schema { 'jordi':
		owner => 'replicator',
	}

}

node 'pgs'
{
	#.30

	class { 'sysctl': }

	class { 'postgresql':
		wal_level => 'hot_standby',
		max_wal_senders => '3',
		checkpoint_segments => '8',
		wal_keep_segments => '8' ,
		hot_standby => true,
		initdb => false,
	}

	class { 'postgresql::streaming_replication':
		masterhost     => '192.168.56.29',
		masterusername => 'replicator',
		masterpassword => 'replicatorpassword',
	}
}
```

## Reference

### classes

#### postgresql

```puppet

#### postgresql::streaming_replication

* **masterhost**: postgres master
* **masterusername**: replication username
* **$masterpassword**: replication password
* **$masterport** (default: port_default)
* **$datadir** (default: datadir_default)

It requires to have **pg_basebackup** and the defined username already create on
the master DB

example:

```puppet
class { 'postgresql::streaming_replication':
  masterhost     => '192.168.56.29',
  masterusername => 'replicator',
  masterpassword => 'replicatorpassword',
}
```

### defines

#### postgresql::role

manages roles (alias users):

* **rolename**: role to define (default: resource's name)
* **password**: password for this role (if it's not a group)
* **login**: boolean, enable or disable login grant (default: true)
* **superuser** boolean, enable or disable superuser grant (default: false)
* **replication** boolean, enable or disable replication grant (default: false)

for example:

```puppet
postgresql::role { 'jordi':
  superuser => true,
  password => 'fuckyeah',
}
```

#### postgresql::schema

Manages schemas:

* **schemaname**: schema to create (default: resource's name)
* **owner**: required, schema's owner

example:

```puppet
postgresql::schema { 'jordidb':
  owner => 'jordi',
}
```

#### postgresql::hba_rule

creates rules to pg_hba:

* **user**: "all", a user name, a group name prefixed with "+", or a
comma-separated list thereof.  In both the DATABASE and USER fields
you can also write a file name prefixed with "@" to include names
from a separate file.

* **database**: "all", "sameuser", "samerole", "replication", a database name,
or a comma-separated list thereof. The "all" keyword does not match "replication".
Access to replication must be enabled in a separate record (see example below).
* **address**: specifies the set of hosts the record matches.  It can be a
host name, or it is made up of an IP address and a CIDR mask that is
an integer (between 0 and 32 (IPv4) or 128 (IPv6) inclusive) that
specifies the number of significant bits in the mask.  A host name
that starts with a dot (.) matches a suffix of the actual host name.
Alternatively, you can write an IP address and netmask in separate
columns to specify the set of hosts.  Instead of a CIDR-address, you
can write "samehost" to match any of the server's own IP addresses,
or "samenet" to match any address in any subnet that the server is
directly connected to.
* **type**: it can be set to:
  * **local** is a Unix-domain socket
  * **host** is either a plain or SSL-encrypted TCP/IP socket,
  * **hostssl** is an SSL-encrypted TCP/IP socket
  * **hostnossl** is a plain TCP/IP socket. (default: host)
* **auth_method**: can be:
  * **trust**
  * **reject**
  * **md5** (default)
  * **password** (clear text passwords!)
  * **gss**
  * **sspi**
  * **krb5**
  * **ident**
  * **peer**
  * **pam**
  * **ldap**
  * **radius**
  * **cert
* **auth_option**: set of options for the authentication in the format
NAME=VALUE.  The available options depend on the different
authentication methods(default: undef)
* **description**: description to identify each rule, see example below (default: resource's name)
* **order**: if any (default: 01)

example:

```puppet
postgresql::hba_rule { 'test':
  user => 'replicator',
  database => 'replication',
  address => '192.168.56.0/24',
}
```
It will create the following pg_hba rule:

```
# rule: test
host	replication	replicator	192.168.56.30/32			md5
```

## Limitations

CentOS 6 only

## Development

We are pushing to have acceptance testing in place, so any new feature should
have some tests to check both presence and absence of any feature

### Contributing

1. Fork it
2. Create your feature branch (`git checkout -b my-new-feature`)
3. Commit your changes (`git commit -am 'Added some feature'`)
4. Push to the branch (`git push origin my-new-feature`)
5. Create new Pull Request
