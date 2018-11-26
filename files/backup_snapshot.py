import logging
import getopt
import sys
import subprocess
import os.path
import smtplib
import datetime, time
import psutil, os
import re
from os import access, R_OK
from ConfigParser import SafeConfigParser
from subprocess import Popen,PIPE,STDOUT
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText

def logAndExit(msg):
    logging.error(msg)
    sys.exit(msg+"\n")

def doLVMSnapshot(lvm_disk, snap_name, snap_size):
    # [root@ip-172-31-46-9 ~]# lvcreate -s -n snap -L 5G /dev/vg/postgres
    #   Logical volume "snap" created.
    # [root@ip-172-31-46-9 ~]# echo $?
    # 0
    # [root@ip-172-31-46-9 ~]#
    p = subprocess.Popen("lvcreate -s -n "+snap_name+" -L "+snap_size+" "+lvm_disk+"2>/dev/null", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    linecount=0
    lastline=""
    for line in p.stdout.readlines():
        lastline = line.strip()
        linecount+=1
    retval = p.wait()

    if retval==0 and linecount==1:
        return snap_name
    else:
        logAndExit('Unable to create lvm snapshot: '+lastline)


def postgresBackupMode(enable = True, backup_name=""):
    global pgusername
    if enable:
        if not backup_name:
            backup_name = "snap."+datetime.datetime.fromtimestamp(time.time()).strftime('%Y%m%d')
        backup_command ='select pg_start_backup("'+backup_name+'");'
    else:
        backup_command = "select pg_stop_backup();"

    psql_command = "psql -U "+pgusername+" -c '"+backup_command+"'"
    logging.debug("postgresBackupMode: "+psql_command)
    p = subprocess.Popen(psql_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in p.stdout.readlines():
        logging.debug("postgresBackupMode: "+line)
    retval = p.wait()

    if retval==0:
        return backup_name
    else:
        logAndExit('Unable to start pg_backup: '+lastline)

def getDisks(pv_disks, tranlate_aws=True):
    disks = []
    regex = re.compile(r"^xv")
    for pv_disk in pv_disks:
        p = subprocess.Popen("lsblk -no pkname "+pv_disk+" | head -n1", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        linecount=0
        lastline=""
        for line in p.stdout.readlines():
            lastline = line.strip()
            linecount+=1
        retval = p.wait()

        if retval==0 and linecount==1:
            if tranlate_aws:
                disks.append("/dev/"+regex.sub('s', lastline))
            else:
                disks.append("/dev/"+lastline)
        else:
            logAndExit('Error getting disk from PV')
    return disks


# thank god for stackoverflow - https://stackoverflow.com/questions/25283882/determining-the-filesystem-type-from-a-path-in-python
def getFSType(path):
    partition = {}
    for part in psutil.disk_partitions(True):
        partition[part.mountpoint] = (part.fstype, part.device)
    if path in partition:
        return partition[path]
    splitpath = path.split(os.sep)
    for i in xrange(len(splitpath),0,-1):
        path = os.sep.join(splitpath[:i]) + os.sep
        if path in partition:
            return partition[path]
        path = os.sep.join(splitpath[:i])
        if path in partition:
            return partition[path]
    return ("unkown","none")

def getDataDir():
    global pgusername
    #psql -U postgres -c 'SHOW data_directory;'
    p = subprocess.Popen("psql -U "+pgusername+" -c 'SHOW data_directory;' | grep -A 1 -- --- | tail -n1", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    linecount=0
    lastline=""
    for line in p.stdout.readlines():
        lastline = line.strip()
        linecount+=1
    retval = p.wait()

    if retval==0 and linecount==1:
        return lastline
    else:
        logAndExit('Error getting datadir')

def getPVs(lvm_disk):
    # busquem vg del lv, dsp pv del vg
    p = subprocess.Popen('lvdisplay '+lvm_disk+' 2>/dev/null | grep "VG Name"', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    linecount=0
    lastline=""
    for line in p.stdout.readlines():
        lastline = line
        linecount+=1
    retval = p.wait()

    if retval==0 and linecount==1:
        line_split = lastline.split()
        if line_split[0]=="VG" and line_split[1]=="Name":
            vg_name = line_split[2]
            pv_disks = []

            p = subprocess.Popen('vgdisplay '+vg_name+' -vv 2>/dev/null  | grep "PV Name"', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for line in p.stdout.readlines():
                line_split = line.split()
                if line_split[0]=="PV" and line_split[1]=="Name":
                    pv_disks.append(line_split[2])
                else:
                    logAndExit('Corrupted output getting PV disk for '+vg_name)
            retval = p.wait()

            if retval!=0:
                logAndExit('ERROR listing PV disks for: '+vg_name)
            else:
                return pv_disks

        else:
            logAndExit('Corrupted output getting VG name: '+lastline)
    else:
        logAndExit('Invalid disk: '+lvm_disk)

lvm_disk = ""
snapshot_size = "5G"
awscli = False
config_file = './postgres_snapshot.config'
logdir = '.'
pgusername = "postgres"

# parse opts

options, remainder = getopt.getopt(sys.argv[1:], 'l:s:ac:', [
                                                            'lvm-disk=',
                                                            "config="
                                                            'snapshot-size=',
                                                            'aws'
                                                         ])

for opt, arg in options:
    if opt in ('-l', '--lvm-disk'):
        lvm_disk = arg
    elif opt in ('-s', '--snapshot-size'):
        snap_size = arg
    elif opt in ('-c', '--config'):
        config_file = arg
    elif opt in ('-a', '--aws'):
        awscli = True
    elif opt in ('-l', '--logdir'):
        logdir = arg
    else:
      sys.exit("unrecoginzed option: ".opt)

logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
rootLogger = logging.getLogger()

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
rootLogger.addHandler(consoleHandler)

if not os.path.isfile(config_file):
    logging.error("Error - config file NOT FOUND ("+config_file+")")
    sys.exit(1)

if not access(config_file, R_OK):
    logging.error("Error reading config file ("+config_file+")")
    sys.exit(1)

try:
    config = SafeConfigParser()
    config.read(config_file)
except Exception, e:
    logging.error("error reading config file - ABORTING - "+str(e))
    sys.exit(1)

try:
    logdir=config.get('pgsnapshot', 'logdir').strip('"')
except:
    logdir=os.path.dirname(os.path.abspath(config_file))

ts = time.time()

logFile = "{0}/{1}/{2}-{3}.log".format(logdir, datetime.datetime.fromtimestamp(ts).strftime('%Y%m%d'), 'pgsnapshot', datetime.datetime.fromtimestamp(ts).strftime('%Y%m%d-%H%M%S'))

current_day_dirname = os.path.dirname(logFile)

try:
    os.makedirs(current_day_dirname)
except Exception, e:
    logging.debug("WARNING - error creating log directory: "+current_day_dirname+" - "+str(e))

fileHandler = logging.FileHandler(logFile)
fileHandler.setFormatter(logFormatter)
rootLogger.addHandler(fileHandler)

rootLogger.setLevel(0)

try:
    lvm_disk=config.get('pgsnapshot', 'lvmdisk').strip('"')
except:
    logging.debug('Using default value for lvm_disk')

try:
    snap_size=config.get('pgsnapshot', 'snapsize').strip('"')
except:
    logging.debug('Using default value for snap_size')

try:
    pgusername=config.get('pgsnapshot', 'pgusername').strip('"')
except:
    logging.debug('Using default value for pgusername')

try:
    awscli=config.getboolean('pgsnapshot', 'aws')
except:
    logging.debug('Using default value for awscli')

if not lvm_disk:
    lvm_disk = getFSType(getDataDir())[1]

pv_disks = getPVs(lvm_disk)

disks = getDisks(pv_disks)

backup_name = postgresBackupMode(True)

print doLVMSnapshot(lvm_disk, backup_name, snap_size)

## temporal
postgresBackupMode(False)
sys.exit("FI")

if awscli:
    import boto3
    import urllib2

    instance_id = urllib2.urlopen('http://169.254.169.254/latest/meta-data/instance-id').read()

    if not instance_id:
      sys.exit("error getting instance_id")

    ec2 = boto3.resource('ec2')

    instance = ec2.Instance(instance_id)

    print(instance.block_device_mappings)
