#!/usr/bin/env python3
#
#  salsa2lp-sync.py
#
#  Copyright 2024 Robert Tari <robert@tari.in>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#

from datetime import datetime, timedelta, timezone
from git import Repo
from launchpadlib.credentials import AccessToken
from launchpadlib.credentials import Consumer
from launchpadlib.credentials import Credentials
from launchpadlib.launchpad import Launchpad
from lazr.restfulclient.errors import HTTPError
from time import sleep
import argparse
import gitlab
import logging
import pathlib
import shutil
import subprocess
import signal
import sys
import tarfile

def onSignal (pSignal, pFrame):

    print ("\nAborting...\n")
    sys.exit (0)

def cleanUp (pPath, lExclude):

    for pChild in pPath.iterdir ():

        if pChild not in lExclude:

            if pChild.is_dir ():

                shutil.rmtree (pChild)

            else:

                pChild.unlink ()

if __name__ == '__main__':

    signal.signal (signal.SIGINT, onSignal)
    lPackages = []
    sHome = pathlib.Path.home ()
    pTempPath = pathlib.Path (sHome, ".cache/salsa2lp-sync")
    pTempPath.mkdir (parents=True, exist_ok=True)
    pCredentials = Credentials ("salsa2lp-sync")
    pConfigDirPath = pathlib.Path (sHome, ".config/salsa2lp-sync")
    pConfigDirPath.mkdir (parents=True, exist_ok=True)
    pCredentialsPath = pathlib.Path (pConfigDirPath, "Credentials.txt")
    pPackagesPath = pathlib.Path (pConfigDirPath, "Packages.txt")
    #formatter_class=argparse.RawDescriptionHelpFormatter,
    pParser = argparse.ArgumentParser (description="Synchronise projects from Salsa to Launchpad", epilog="You must call the script manually the first time. It will give you a Launchpad link, which you need to open in a browser to grant it access (not necessarily on the same system). Select 'Change Anything' for the access level.\n\nCalling the script without a project argument will go through all projects on https://salsa.debian.org/ubports-team, as well as the ~/.config/salsa2lp-sync/Packages.txt file.\n\nCalling the script with a project argument will process only that particular project.")
    pParser.add_argument ("-t", "--team", default="lomiri", help="The Launchpad team whose PPA the projects are to be synchronised to (defaults to \"lomiri\")")
    pParser.add_argument ("-p", "--ppa", default="builds", help="The Launchpad PPA the projects are to be synchronised to (defaults to \"builds\")")
    pParser.add_argument ("-v", "--verbose", action="store_true", help="Be more verbose (unset by default)")
    pParser.add_argument ("project", metavar="PROJECT", nargs='?', help="The project to be synchronised")
    pArgs = pParser.parse_args ()

    if pArgs.verbose:
        logging.basicConfig(level=logging.INFO)

    if pArgs.project:

        sFile = pPackagesPath.read_text ()
        lLines = sFile.splitlines()
        sTeam = "ubports-team"

        for sLine in lLines:

            sLinePackage, sLineTeam = sLine.split (" ")

            if pArgs.project == sLinePackage:

                sTeam = sLineTeam

                break

        lPackages.append ({"package": pArgs.project, "team": sTeam})

    else:

        # Get all projects from Salsa
        pGitlab = gitlab.Gitlab ("https://salsa.debian.org")
        pGroup = pGitlab.groups.get (id="ubports-team", lazy=True)
        lProjects = pGroup.projects.list (get_all=True, order_by="name", sort="asc")

        for pProject in lProjects:

            lPackages.append ({"package": pProject.name, "team": "ubports-team"})
        #~Get all projects from Salsa

        # Get all the projects from Packages.txt
        sFile = pPackagesPath.read_text ()
        lLines = sFile.splitlines()

        for sLine in lLines:

            sPackage, sTeam = sLine.split (" ")
            lPackages.append ({"package": sPackage, "team": sTeam})
        #~Get all the projects from Packages.txt

    if pCredentialsPath.is_file ():

        pFile = open (pCredentialsPath)
        pCredentials.load (pFile)
        pFile.close ()

    else:

        sToken = pCredentials.get_request_token (web_root="production")
        bComplete = False
        bUrlShown = False

        while not bComplete:

            try:
                pCredentials.exchange_request_token_for_access_token (web_root="production")
                pFile = open (pCredentialsPath, 'w')
                pCredentials.save (pFile)
                pFile.close ()
                bComplete = True

            except HTTPError:

                if not bUrlShown:

                    print ("\n{sToken}\n")
                    bUrlShown = True

                sleep (1)

    pLaunchpad = Launchpad.login_with ("salsa2lp-sync", "production", credentials_file=pCredentialsPath, version="devel")
    pGroup = pLaunchpad.people[pArgs.team]

    for dPackage in lPackages:

        # Clean up
        cleanUp (pTempPath, [])
        #~Clean up

        # Get the Debian folder
        pSalsaPath = pathlib.Path (pTempPath, "salsa")

        # FIXME: Handle gbp-managed packages gracefully here, too...

        try:

            Repo.clone_from (f"https://salsa.debian.org/{dPackage['team']}/{dPackage['package']}.git", pSalsaPath)

        except:

            print (f"\nPanic: {dPackage['package']} not found on Salsa\n")

            continue
        #~Get the Debian folder


        # Check for missing debian content
        lDebianFiles = ["rules", "changelog", "control"]
        bMissing = False

        for sDebianFile in lDebianFiles:

            pDebianFilePath = pathlib.Path (pSalsaPath, "debian", sDebianFile)

            if not pDebianFilePath.is_file ():

                print (f"\nPanic: {dPackage['package']} is missing 'debian/{sDebianFile}'\n")
                bMissing = True

        if bMissing:

            continue
        #~Check for missing debian content

        # Get the package format
        bNative = False

        try:

            pSubprocess = subprocess.run (["dpkg-source", "--print-format", pSalsaPath], check=True, capture_output=True, text=True)
            sFormat = pSubprocess.stdout.strip ()
            bNative = (sFormat == "3.0 (native)")

        except subprocess.CalledProcessError as pException:

            print (f"\nPanic: Failed getting package format for {dPackage['package']}:\n{pException}\n")

            continue
        #~Get the package format

        # Get the package version
        sVersion = None

        try:

            pSubprocess = subprocess.run (["dpkg-parsechangelog", "--show-field", "Version"], cwd=pSalsaPath, check=True, capture_output=True, text=True)
            sVersion = pSubprocess.stdout.strip ()

        except subprocess.CalledProcessError as pException:

            print (f"\nPanic: Failed getting package version for {dPackage['package']}:\n{pException}\n")

            continue
        #~Get the package version

        sDistribution = None

        # Get the package distribution
        try:

            pSubprocess = subprocess.run (["dpkg-parsechangelog", "--show-field", "Distribution"], cwd=pSalsaPath, check=True, capture_output=True, text=True)
            sDistribution = pSubprocess.stdout.strip ()

            if sDistribution == "UNRELEASED":

                sDistribution = "pre-release"

            else:

                sDistribution = "release"

        except subprocess.CalledProcessError as pException:

            print (f"\nPanic: Failed getting package distribution for {dPackage['package']}:\n{pException}\n")

            continue
        #~Get the package distribution

        # Download the tarball
        if not bNative:

            try:

                # FIXME: prefer debian/rules get-orig-source, if present
                subprocess.run (["uscan", "--noconf", "--rename", "--download-current-version", "--destdir=."], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, cwd=pSalsaPath, check=True)

            except subprocess.CalledProcessError as pException:

                print (f"\nPanic: Failed calling 'uscan' for {dPackage['package']}:\n{pException}\n")

                continue

            cleanUp (pTempPath, [pSalsaPath])
        #~Download the tarball

        # Create a new repository or pull the code from Launchpad
        pRepository = pLaunchpad.git_repositories.getByPath (path=f"~{pArgs.team}/+git/{dPackage['package']}")
        bNewRepo = False

        if not pRepository:

            print (f"{dPackage['package']}: Creating repository")
            pRepository = pLaunchpad.git_repositories.new (name=dPackage["package"], owner=pGroup, target=pGroup)
            bNewRepo = True

        pNow = datetime.now (timezone.utc)
        pExpires = pNow + timedelta (seconds=3600)
        sExpires = pExpires.isoformat ()
        sAccessToken = pRepository.issueAccessToken (description=f"Access token for {pLaunchpad.me.name}", scopes=["repository:push", "repository:pull"], date_expires=sExpires)
        pRepo = Repo.init (pTempPath)
        pMain = pRepo.create_remote ("main", url=f"https://{pLaunchpad.me.name}:{sAccessToken}@git.launchpad.net/~{pArgs.team}/+git/{dPackage['package']}")

        if not bNewRepo:

            pMain.fetch ("main")
            pRepo.create_head ("main", pMain.refs.main)
            pRepo.heads.main.checkout ()
            pMain.pull ("main:main")
        #~Create a new repository or pull the code from Launchpad

        # Remove current source tree
        pGitPath = pathlib.Path (pTempPath, ".git")
        cleanUp (pTempPath, [pGitPath, pSalsaPath])
        #~Remove current source tree

        # Extract the tarball
        if not bNative:

            lSuffixes = ["xz", "bz2", "gz"]
            sCompression = None
            sTarPath = None

            for sSuffix in lSuffixes:

                lTarPaths = list (pSalsaPath.glob (f"*.tar.{sSuffix}"))

                if lTarPaths:

                    sTarPath = lTarPaths[0]
                    sCompression = sSuffix

                    break

            with tarfile.open (sTarPath, f"r:{sCompression}") as pTarFile:

                lMembers = pTarFile.getmembers ()
                pToplevelPath = pathlib.Path (lMembers[0].name).parts[0]

                for pMember in lMembers:

                    pMemberPath = pathlib.Path (pMember.name)
                    pMember.name = pMemberPath.relative_to (pToplevelPath)

                    if str (pMember.name) == "debian" or (pMember.name.parts and pMember.name.parts[0] == "debian"):

                        continue

                    if sys.version_info >= (3, 12):

                        pTarFile.extract (pMember, pTempPath, filter="fully_trusted")

                    else:

                        pTarFile.extract (pMember, pTempPath)
        #~Extract the tarball

        # Get the last commit
        pSalsaRepo = Repo.init (pSalsaPath)
        sCommit = pSalsaRepo.head.commit.hexsha
        #~Get the last commit

        # Move files and delete the Salsa folder
        if not bNative:

            pOldPath = pathlib.Path (pSalsaPath, "debian")
            pNewPath = pathlib.Path (pTempPath, "debian")
            pOldPath.rename (pNewPath)

        else:

            for pChild in pSalsaPath.iterdir ():

                if pChild.name != ".git":

                    pOldPath = pathlib.Path (pSalsaPath, pChild.name)
                    pNewPath = pathlib.Path (pTempPath, pChild.name)
                    pOldPath.rename (pNewPath)

        cleanUp (pSalsaPath, [])
        pSalsaPath.rmdir ()
        #~Move files and delete the Salsa folder

        # Push the changes to Launchpad
        if bNewRepo or pRepo.is_dirty (untracked_files=True):

            print (f"{dPackage['package']}: Pushing changes to Launchpad")
            pRepo.git.add ("-A", "--force")
            pRepo.index.commit (f"Update from salsa.debian.org: {dPackage['package']} {sDistribution} {sVersion} (commit: {sCommit})")

            if bNewRepo:

                pRepo.create_head ("main")
                pRepo.heads.main.checkout ()

            pMain.push ("main:main").raise_if_error ()
        #~Push the changes to Launchpad

        """
        # Create/update build recipes (multiple distro series)
        pArchive = pGroup.getPPAByName (name=pArgs.ppa)

        for pDistroseries in pLaunchpad.distributions["ubuntu"].series:

            if float (pDistroseries.version) >= 24.04:

                sRecipe = f"{dPackage['package']}-{pDistroseries.version}"
                pRecipe = pGroup.getRecipe (name=sRecipe)
                sRecipeText = "# git-build-recipe format 0.4 deb-version " + sVersion + "~{revtime}\nlp:~" + pArgs.team + "/+git/" + dPackage["package"] + " main"

                if not pRecipe:

                    print (f"{dPackage['package']}: Creating build recipe {sRecipe}")
                    pGroup.createRecipe (build_daily=True, daily_build_archive=pArchive, description=f"Daily build of {dPackage['package']}", distroseries=pDistroseries, name=sRecipe, recipe_text=sRecipeText)

                else:

                    sCurrentRecipeText = pRecipe.recipe_text.strip ()

                    if sCurrentRecipeText != sRecipeText:

                        print (f"{dPackage['package']}: Updating build recipe {sRecipe}")
                        pRecipe.recipe_text = sRecipeText
                        pRecipe.lp_save ()
        #~Create/update build recipes (multiple distro series)
        """

        # Create/update the build recipe (one distro series)
        pRecipe = pGroup.getRecipe (name=dPackage["package"])
        sRecipeText = "# git-build-recipe format 0.4 deb-version " + sVersion + "~{revtime}\nlp:~" + pArgs.team + "/+git/" + dPackage["package"] + " main"

        if not pRecipe:

            print (f"{dPackage['package']}: Creating the build recipe")
            pArchive = pGroup.getPPAByName (name=pArgs.ppa)
            pDistroseries = pLaunchpad.distributions["ubuntu"].getSeries (name_or_version="24.04")
            pGroup.createRecipe (build_daily=True, daily_build_archive=pArchive, description=f"Daily build of {dPackage['package']}", distroseries=pDistroseries, name=dPackage["package"], recipe_text=sRecipeText)

        else:

            sCurrentRecipeText = pRecipe.recipe_text.strip ()

            if sCurrentRecipeText != sRecipeText:

                print (f"{dPackage['package']}: Updating the build recipe")
                pRecipe.recipe_text = sRecipeText
                pRecipe.lp_save ()
        #~Create/update the build recipe (one distro series)

    # Clean up
    cleanUp (pTempPath, [])
    #~Clean up

    sys.exit (0)
