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
import syslog
import os

from boto.route53.connection import Route53Connection
from boto.route53.record import ResourceRecordSets
from boto.route53.exception import DNSServerError

def myLog(message):
    procName = __file__
    syslogMsg = procName + ": " + message
    syslog.syslog(syslogMsg)
    print '%s' % message

# get the FQDN
# the domain is specified on the command line, hostname we get from the system
if len(sys.argv) == 2:
    from socket import gethostname
    hostname = gethostname()
    domainname = sys.argv[1]

    if domainname[0] != ".":
        domainname = "." + domainname

    fqdn = hostname + domainname

    myLog("FQDN: %s" % fqdn)
else:
    myLog("No domain component specified on command line")
    sys.exit(1)

try:
    hostname
except NameError:
    myLog("Unable to read hostname")
    sys.exit(1)

# Add trailing dot to hostname if it doesn't have one
if fqdn[-1:] != ".":
    fqdn += "."

# Get current IP
try:
    myLog("Getting public IP from instance metadata service")
    ipsite = urllib.urlopen('http://169.254.169.254/latest/meta-data/public-ipv4')
except:
    myLog("Connection error getting IP address")
    sys.exit(1)

response = ipsite.read()
ips = re.findall("(?:\d{1,3}\.){3}\d{1,3}", response)
if type(ips) in [list,  tuple,  set]:
    for record in ips:
        newip = record
try:
    newip
except NameError:
    myLog("Unable to find IP address in response from check site")
    sys.exit(1)

# Verify it's a good ip
try:
    socket.inet_aton(newip)
except socket.error:
    myLog("Received invalid IP address")
    sys.exit(1)

myLog("Current Public IP: %s" % newip)

# Initialize the connection to AWS Route53
if awskeyid and awskeysecret:
    route53 = Route53Connection(awskeyid, awskeysecret)
else:
    route53 = Route53Connection()

# Get the zoneid
try:
    route53zones = route53.get_all_hosted_zones()
except DNSServerError,  e:
    myLog("Connection error to AWS. Check your credentials")
    myLog("Error %s - %s" % (e.code,  str(e)))
    sys.exit(1)

for zone in route53zones['ListHostedZonesResponse']['HostedZones']:
    if zone['Name'][0:-1] in fqdn:
        zoneid = zone['Id'].replace('/hostedzone/', '')
        myLog("Found Route53 Zone %s for fqdn %s" % (zoneid,  fqdn))

try:
    zoneid
except NameError:
    myLog("Unable to find Route53 Zone for %s" % fqdn)
    sys.exit(1)

# Find the old record if it exists
try:
    sets = route53.get_all_rrsets(zoneid)
except DNSServerError,  e:
    myLog("Connection error to AWS")
    myLog("Error %s - %s" % (e.code,  str(e)))
    sys.exit(1)

for rset in sets:
    if rset.name == fqdn and rset.type == 'A':
        curiprecord = rset.resource_records
        if type(curiprecord) in [list, tuple, set]:
            for record in curiprecord:
                curip = record
        myLog("Current DNS IP: %s" % curip)
        curttl = rset.ttl
        myLog("Current DNS TTL: %s" % curttl)

        if curip != newip:
            # Remove the old record
            myLog("Removing old record from Route53...")
            change1 = ResourceRecordSets(route53, zoneid)
            removeold = change1.add_change("DELETE", fqdn, "A", curttl)
            removeold.add_value(curip)
            change1.commit()
        else:
            myLog("IPs match in DNS, no DNS changes being made")
            sys.exit(0)

try:
    curip
except NameError:
    myLog("FQDN %s not found in current zone record" % fqdn)

# Add the new record
myLog("Adding %s to DNS as %s..." % ( fqdn,  newip))
change2 = ResourceRecordSets(route53, zoneid)
change = change2.add_change("CREATE", fqdn, "A", 60)
change.add_value(newip)
change2.commit()
