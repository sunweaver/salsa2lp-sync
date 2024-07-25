# LomiriForUbuntu.py

## Dependecies

 - python3-launchpadlib
 - python3-git
 - python3-gitlab
 - devscripts

## Setup

 - Can only be run on a Debian-based system
 - Copy `LomiriForUbuntu.py` to a location of your choice

## Usage

You must call the script manually the first time. It will give you a
Launchpad link, which you need to open in a browser to grant it access
(not necessarily on the same system). Your credentials will be stored in
`~/LomiriForUbuntu/Credentials.txt`

Calling the script without arguments will go through all projects on
https://salsa.debian.org/ubports-team.

Calling the script with a project argument will process only that
particular project. For example:

```
./LomiriForUbuntu.py lomiri-api
```

## Misc

There is no error handling at this stage. We want the script to crash
spectacularly to get as much error info as possible.
