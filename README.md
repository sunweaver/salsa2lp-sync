# LomiriForUbuntu.py

## Dependecies

 - python3-launchpadlib
 - python3-git
 - python3-gitlab
 - devscripts

## Setup

 - Can only be run on a Debian-based system
 - Copy `LomiriForUbuntu.py` to a location of your choice
 - Set `TEMP_PATH` and `CREDENTIALS_PATH` to suit your system

## Usage

Calling the script without arguments will go through all projects on
https://salsa.debian.org/ubports-team.

Calling the script with a project argument will process only that
particular project. For example:

```
./LomiriForUbuntu.py lomiri-api
```


