#!/usr/bin/python -u

import os
import re
import sys
import rpm
import ConfigParser

# This program will scan through a bunch of folders in a repository, and
# remove duplicate packages. The idea is that redhat provides binaries 
# that we don't want, but may interefere with their replacements.
# By removing them, we can simplify things later on in the process.

# This script can evaluate which source is correct based on architecture,
# age, or location. More to come if desired. These settings are all set 
# by the configuration file found in this same directory, or the config
# file passed in on the command line. I don't think there is a nice way
# to provide a cli for this, so I won't.

# General flow:
 # Read config
 # Scan repository, generate list of packages with duplicate names
 # Pick the best one based on the config file criteria such as:
  # Where are they from?
  # What version are they?
  # When were they added?
  # Specific exceptions?
 # what it does with these duplicates is also configurable:
  # Delete them
  # List them

def readConfig(configFile):
 # This was originally written for a different script, so the names are
 # weird, but the idea works fine. Basically, it returns global options
 # as options, and a list of dictionaries of the later config sections
 # as containers. Note that all of the global configuration may be read
 # from the containers, and that you may use recursive substitution by
 # using <tags>.
  containers = {}
  config = ConfigParser.ConfigParser()
  if not(os.path.isfile(configFile)):
    sys.exit("The config file "+configFile+" is not a file. That is unfortunate.")
  if config.read(configFile):
    sections = {}
    for i in config.sections():
      sections[i] = config.items(i)
  else:
    sys.exit("Config File is not valid.")
  if "main" in sections.keys():
    options = {}
    for i in sections["main"]:
      options[i[0]] = i[1]
  else:
    options = None
    print "No global options found. Strange. I might explode."
  for i in sections.keys():
    if not i == "main":
      containers[i] = {}
      for j in sections[i]:
        containers[i][j[0]] = j[1]
      if not "section" in containers[i].keys():
        containers[i]["section"] = i
  if options:
    options = replaceKeys(options, {})
  containers = [replaceKeys(containers[x], options) for x in containers]
  return containers, options

def replaceKeys(container, main):
  if main:
    for i in main.keys():
      if not i in container.keys():
        container[i] = main[i]
  madeProgress = True
  keysWithSubs = remainingSubs(container)
  while keysWithSubs and madeProgress:
    madeProgress = False
    for j in keysWithSubs.keys():
      if not any(map(lambda x: x in keysWithSubs.keys(), keysWithSubs[j])):
        for k in keysWithSubs[j]:
          if k in container.keys():
            container[j] = re.sub("<"+k+">", container[k], container[j])
            madeProgress = True
    keysWithSubs = remainingSubs(container)
  return container
  
def remainingSubs(container):
  keysWithSubs = {}
  for i in container.keys():
    if re.findall(".*<(.+?)>.*", container[i]):
      keysWithSubs[i] = re.findall(".*<(.+?)>.*", container[i])
  return keysWithSubs

def main():
  if len(sys.argv) >= 2:
    configFile = sys.argv[1]
  else:
    configFile = "./duplicateCheck.conf"
  repositories, options = readConfig(configFile)
  for i in repositories:
    duplicates = getDups(i)
    priorities = getPriorities(i)
    i['ideal_packages'] = []
    for j in duplicates.keys():
      for sortMethod in priorities:
        idealPackage = sortMethod(duplicates[j], i)
        if idealPackage:
          i['ideal_packages'].append(idealPackage)
          break
    for j in i['ideal_packages']:
      print j[0], j[1]['version']
      

def getDups(repository):
  files = {}
  ts = rpm.TransactionSet()
  allFiles = {}
  for root, dirs, files in os.walk(repository['location']):
    for file in files:
      if readRpmHeader(ts, os.path.join(root, file)):
        allFiles[os.path.join(root, file)] = readRpmHeader(ts, os.path.join(root, file))
  fileNames = [allFiles[i]['name'] for i in allFiles.keys()]
  setNames = list(set(fileNames))
  for i in setNames:
    fileNames.remove(i)
  duplicates = {}
  for i in fileNames:
    for j in allFiles.keys():
      if allFiles[j]['name'] == i:
        if i in duplicates.keys():
          duplicates[i].append((j, allFiles[j]))
        else:
          duplicates[i] = [(j, allFiles[j])]
  return duplicates

def readRpmHeader(ts, filename):
    """ Read an rpm header. """
    ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)
    fd = os.open(filename, os.O_RDONLY)
    h = None
    try:
        h = ts.hdrFromFdno(fd)
    except rpm.error, e:
        if str(e) == "public key not available":
            print str(e)
        if str(e) == "public key not trusted":
            print str(e)
        if str(e) == "error reading package header":
            print str(e)
        h = None
    finally:
        os.close(fd)
    return h

def getPriorities(repository):
  return [sortByAge, sortByVersion, sortByLocation]

def sortByAge(packages, repository):
  return packages[0]

def sortByVersion(packages, repository):
  values = [x.dsOfHeader() for x in packages]
  return __bestByValues(packages, values)

def sortByLocation(packages, repository):
  return packages[0]      

def __bestByValues(packages, values):
  return packages[0]
main()
