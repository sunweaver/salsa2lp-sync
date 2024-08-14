# salsa2lp-sync

## Dependecies

 - python3-launchpadlib
 - python3-git
 - python3-gitlab
 - devscripts

## Setup

 - Can only be run on a Debian-based system
 - Save `salsa2lp-sync.py` to a location of your choice
 - Save `Packages.txt` to `~/.config/salsa2lp-sync/Packages.txt`

## Usage

`salsa2lp-sync.py [-h] [-t TEAM] [-p PPA] [PROJECT]`

### Positional arguments:

PROJECT

The project to be synchronised

### Options:

-h, --help

Show the help message and exit

-t TEAM, --team TEAM

The Launchpad team whose PPA the projects are to be synchronised to

-p PPA, --ppa PPA

The Launchpad PPA the projects are to be synchronised to

---

You must call the script manually the first time. It will give you a
Launchpad link, which you need to open in a browser to grant it access
(not necessarily on the same system). Select "**Change Anything**" for
the access level.

Your credentials will be stored in `~/.config/salsa2lp-sync/Credentials.txt`.

Calling the script without a project argument will go through all
projects on https://salsa.debian.org/ubports-team, as well as the
`~/.config/salsa2lp-sync/Packages.txt` file.

Calling the script with a project argument will process only that
particular project. For example:

```
./salsa2lp-sync.py lomiri-api
```
