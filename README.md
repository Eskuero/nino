
# Nino: Keep your apps updated

Do you want latest features first than anyone? Or do you want to build from source code because you do not fully trust the binaries distributed by the developer/manufacturer?

Then you can use nino to automatically manage sync, build, sign and deploy all of your open source Android apps.


- [Installation](#installation)
    - [Runtime dependencies](#runtime-dependencies)
- [Configuration](#configuration)
    - [TOML file](#toml-file)
    - [Command line arguments](#command-line-arguments)
- [Understanding](#understanding)
    - [Syncing](#syncing)
        - [Custom fetcher](#custom-fetcher)
        - [Preserving local changes](#preserving-local-changes)
    - [Building](#building)
        - [Gradle tasks](#gradle-tasks)
        - [Entrypoint](#entrypoint)
        - [Forcing](#forcing)
    - [Signing](#signing)
    - [Deploying](#deploying)
    - [Retrying](#retrying)
# Installation
Clone this git repository and install it using pip:
```
$ git clone https://github.com/Eskuero/nino.git
$ cd nino
# pip install .
```
### Runtime dependencies
The following utils must be avalaible from PATH during execution
- Python 3 - [https://www.python.org/downloads/](https://www.python.org/downloads/)
- Toml python library (automatically installed by pip) - [https://github.com/uiri/toml](https://github.com/uiri/toml)
- Java OpenJDK 8 - [https://openjdk.java.net/install/index.html](https://openjdk.java.net/install/index.html)
- Android SDK (adb, apksigner, zipalign) - [https://developer.android.com/studio/#command-tools](https://developer.android.com/studio/#command-tools)
- Gradle (for projects not providing a wrapper) - [https://gradle.org/install/](https://gradle.org/install/)
- Git - [https://git-scm.com/book/en/v2/Getting-Started-Installing-Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
- Mercurial - [https://www.mercurial-scm.org/downloads](https://www.mercurial-scm.org/downloads)

#### Windows
The easiest integration with Windows is achieved by installing everything via chocolatey on an elevated PS terminal:
```
> choco install git hg python3 gradle jdk8 android-sdk
```
Then you will need to manually install the latest build-tools and add them to your PATH:
```
> sdkmanager.bat "build-tools;29.0.2"
> $oldpath = (Get-ItemProperty -Path 'Registry::HKEY_CURRENT_USER\Environment' -Name PATH).path
> $newpath ="$oldpath;C:\Android\android-sdk\build-tools\29.0.2"
> Set-ItemProperty -Path 'Registry::HKEY_CURRENT_USER\Environment' -name PATH -Value $newpath
```
Logging off and in may be required for the changes to be applied.
####

Each project may have additional dependencies.
# Configuration
## TOML file
The most convenient method for configuration is a toml file. Nino will automatically load the nino.toml file if found on the working directory. This allow providing defaults for all the options as well as granular control per project specific.
For additional information on how TOML works and how you should structure your file you can review the official documentation at
[https://github.com/toml-lang/toml/blob/master/README.md](https://github.com/toml-lang/toml/blob/master/README.md)

In the following example:
- We define a keystore named "store2", which references the file "clave.jks".
- Inside that file there's a "mykey" key alias that we will reference from now on by the name of "key2"
- We also enable **syncing/building/preserving changes for all the projects** and signing them using the **key "mykey"** from the **keystore "clave.jks"**.
- You could also set a keystore/key combination per project or even per task outputs specific.

Per project specific we have the following settings:
- **fenix** project will always execute two tasks:
  - clean, that matches the "clean" gradle task
  - production, that matches the "assembleFenixProduction" gradle task
- **Signal-Android** project it would always force building of the app using the "assembleWebsiteRelease" gradle task.
```
[keystores]
    [keystores.store2]
        path = "clave.jks"
        [keystores.store2.aliases.key2]
            name = "mykey"

[projects]
        [projects.default]
                sync = true
                preserve = true
                build = true
                keystore = "store2"
                keyalias = "key2"
        [projects.fenix]
                [projects.fenix.tasks.clean]
                        exec = "clean"
                [projects.fenix.tasks.production]
                        exec = "assembleFenixProduction"
        [projects.Signal-Android]
                force = true
                [projects.Signal-Android.tasks.websiterelease]
                        exec = "assembleWebsiteRelease"
```
## Command line arguments
It's indeed possible to override the default options (not the project specific ones) defined on the toml file by passing command line arguments as described below:
```
$ nino --help
usage: nino [-h] [-f FORCE] [-r] [--version]

optional arguments:
  -h, --help            show this help message and exit
  -f FORCE, --force FORCE
                        Force build of a project even without changes
  -r, --retry           Retry failed tasks from previous run
  --version             show program's version number and exit
```
Per example we could force building of KISS and Signal-Android project using arguments like this:
```
$ nino --force KISS -f Signal-Android
```
# Understanding
For each project nino will follow this four indepent steps: Syncing --> Building --> Signing --> Deploying
## Syncing
This is the first stage entered during a normal run. Nino will retrieve latest changes by querying remotes and then apply those on the local working copy.

Supported syncing methods are automatically detected without configuration and follow this priority when choosing one for each project: Custom script > Git > Mercurial
#### Custom fetcher
If an executable named nino-sync is found on the project folder root it will be used. The custom script may support the following arguments for a variety of tasks:
- lastdate: Print via stdout the age of the last time the project was updated.
- changes: Must store somewhere safe the local uncommitted changes to the project for later restore and have a return code of 0 if changes are to be restored.
- fetch: Fetch changes from remote (not merge them). Return 0 if it went okey.
- updated: Return 0 if there are new changes to be merged after fetch operation.
- merge: Apply new changes to the local copy (will only be called if updated operation returned 0.
- restore: Try to apply back the local uncommitted changes that were saved during the "changes" operation.
#### Preserving local changes
Sometimes you may have local changes that are not committed to the local SCM database but still need to hold onto them for a variety of reasons.

Nino can achieve this by diffing the local repository before syncing and then trying to apply it again over the local copy. Note that failure to re-apply will not halt the building process for the project.
## Building
This is the second stage entered during a normal run. Normally nino would only build the project when new changes are detected and applied during then syncing process.

Is required to provide a keystore and keyalias for each project that has building enabled.
#### Gradle tasks
By default the building process in nino is set to run a single 'assembleRelease' gradle task for the project. This can be override on the toml configuration file to use one, various or even none tasks.
#### Entrypoint
Certain complex projects like Orbot, Firefox or VLC require native libraries built outside of gradle so you need to manually build them. For this you can provide an 'nino-entrypoint' executable and it will be run before attempting any gradle task.
#### Forcing
Sometimes you may want to force building of a certain project even if no new changes were pulled from the remote during this iteration. This setting will only have effect if building is enabled for that project as well.
```
if building and (changed or forcing)
```
## Signing
This is the third stage entered during a normal run. Nino now will search the project folder for outputs to sign. Apk files found in paths that do not match the regex rule ".\*build/outputs/apk/\*" will be filtered out as the suppossedly where not built by gradle.

Remaining outputs will be signed using the configured key and moved into the final directory "NINO-RELEASES". Naming convention for the moved file will be "ProjectName-BuildFlavour-Buildtype.apk".

Per example the assembleBlueRelease of a Tusky project will provide a signed file like "Tusky-blue-release.apk".
## Deploying
This is the final stage entered during a normal run. By now nino will have a list of all the outputs that were moved into the NINO-RELEASES folder for this project.

DEPLOYING VIA ADB IS NOW DEPRECATED AND WILL BE REMOVED AS SOON AS SOON AS OTHER METHODS ARE MERGED IN
```
Then for each device device configured each one of the outputs will be deployed via adb. The installation will timeout at 15 seconds if the specified device ID is not attached.

For more information regarding adb usage and connection see the official documentation:
<https://developer.android.com/studio/command-line/adb>
```

## Retrying
Retrying is not a program stage rather than a mode. Nino always saves a json formatted report of the run into a .nino-last file. When we enter retry mode only the failed steps from the previous run are attempted, thus saving a lot of time by skipping projects and stages that went just fine.

A good example of this is when you forget to attach your phone via USB so deployment fails. Then you can run nino in retry mode and only attempt to deploy the outputs that failed to install.

Note that retry mode will always use the configuration from the previous run, so toml config file and command line options will be ignored.
