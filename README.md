# Music Database
## Table of Contents
* [General Info](#general-info)
* [Technologies](#technologies)
* [Installation](#installation)

## General Info
This is a basic database which pulls from the Spotify Web API and stores songs that the user wants to be organised using databases.

## Technologies
Project is created with:
* Python 3.12.6
* Flask 3.03
* Bootstrap 4
* Spotipy Web API
* Sqlite3

## Installation
### Virtual Environment
Virtualenv must be installed, create a virtual environment in the app directory, everything will be installed with the virtual environment. <br />
<br />
To create the environment, run this command in bash:
```
$ virtualenv venv
```
To activate it run this command if on Windows system:
```
$ venv\Scripts\activate
```
Or this command if on Linux/Mac system:
```
$ source venv/bin/activate
```

### Requirements
Pip will be used for installtion of the dependencies, the following will need to be installed onto the virtual environment: <br />
* Flask 3.03
* Pysqlite3 0.5.3
* Spotipy 2.24.0
