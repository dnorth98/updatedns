#!/usr/bin/env python

"""
 Update DNS Entry in Amazon Route53 via boto
-------------------------------------------------------------------
 Creator: Brian Parsons <brian@pmex.com>
 Modified: Dave North <dnorth98@gmail.com>

 Requires: boto  - http://boto.cloudhackers.com/en/latest/index.html

 Variables:
---------------

awskeyid - Amazon AWS Credentials Security Key ID
awskeysecret - Amazon AWS Secret that matches the security key id

NOTE: If no keys are provided, instance role credentials will be used

"""

##
## SET CONFIGURATION VARIABLES
##

awskeyid = ""
awskeysecret = ""

##
## END OF VARIABLES
##

import re
import socket
import sys
import urllib

from boto.route53.connection import Route53Connection
from boto.route53.record import ResourceRecordSets
from boto.route53.exception import DNSServerError

# Find hostname from system if not specified on command line
if len(sys.argv) == 2:
    hostname = sys.argv[1]
else:
    from socket import gethostname
    hostname = gethostname()

try:
    hostname
except NameError:
    print 'Hostname not specified and not able to detect.'
    sys.exit(1)

# Add trailing dot to hostname if it doesn't have one
if hostname[-1:] != ".":
    hostname += "."

print 'Hostname: %s' % hostname

# Get current IP
try:
    ipsite = urllib.urlopen('http://checkip.dyndns.org')
except:
    print 'Connection error getting IP address.'
    sys.exit(1)

response = ipsite.read()
ips = re.findall("(?:\d{1,3}\.){3}\d{1,3}", response)
if type(ips) in [list,  tuple,  set]:
    for record in ips:
        newip = record
try:
    newip
except NameError:
    print 'Unable to find IP address in response from check site.'
    sys.exit(1)

# Verify it's a good ip
try:
    socket.inet_aton(newip)
except socket.error:
    print 'Received invalid IP address.'
    sys.exit(1)

print 'Current IP: %s' % newip

# Initialize the connection to AWS Route53
if awskeyid and awskeysecret:
    route53 = Route53Connection(awskeyid, awskeysecret)
else:
    route53 = Route53Connection()

# Get the zoneid
try:
    route53zones = route53.get_all_hosted_zones()
except DNSServerError,  e:
    print 'Connection error to AWS. Check your credentials.'
    print 'Error %s - %s' % (e.code,  str(e))
    sys.exit(1)

for zone in route53zones['ListHostedZonesResponse']['HostedZones']:
    if zone['Name'][0:-1] in hostname:
        zoneid = zone['Id'].replace('/hostedzone/', '')
        print 'Found Route53 Zone %s for hostname %s' % (zoneid,  hostname)

try:
    zoneid
except NameError:
    print 'Unable to find Route53 Zone for %s' % hostname
    sys.exit(1)

# Find the old record if it exists
try:
    sets = route53.get_all_rrsets(zoneid)
except DNSServerError,  e:
    print 'Connection error to AWS.'
    print 'Error %s - %s' % (e.code,  str(e))
    sys.exit(1)

for rset in sets:
    if rset.name == hostname and rset.type == 'A':
        curiprecord = rset.resource_records
        if type(curiprecord) in [list, tuple, set]:
            for record in curiprecord:
                curip = record
        print 'Current DNS IP: %s' % curip
        curttl = rset.ttl
        print 'Current DNS TTL: %s' % curttl

        if curip != newip:
            # Remove the old record
            print 'Removing old record...'
            change1 = ResourceRecordSets(route53, zoneid)
            removeold = change1.add_change("DELETE", hostname, "A", curttl)
            removeold.add_value(curip)
            change1.commit()
        else:
            print 'IPs match,  not making any changes in DNS.'
            sys.exit(0)

try:
    curip
except NameError:
    print 'Hostname %s not found in current zone record' % hostname


# Add the new record
print 'Adding %s to DNS as %s...' % ( hostname,  newip)
change2 = ResourceRecordSets(route53, zoneid)
change = change2.add_change("CREATE", hostname, "A", 60)
change.add_value(newip)
change2.commit()

