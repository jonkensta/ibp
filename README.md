# About
This repository hosts the Inside Books Project database web interface.
This interface is implemented using Bottle and SQLAlchemy and includes the following features:
  - creating processing labels
  - querying inmate data from the TDCJ and FBOP websites,
  - printing warnings and alerts for inmates,

# Installation
Installing and running this software requires several steps.
First, you must clone this repository with submodules.
Then, the Python and HTML/CSS/JS dependencies must be installed.
Finally, you must configure the application and initialize the database.

## Meeting Dependencies
All of the Python dependencies must be installed as given in [the requirements file](requirements.txt).
It is recommended that these be installed in a virtual environment by first doing the following:
```bash
python -m venv venv
source venv/bin/activate
```
followed by
```bash
pip install -r requirements.txt
```
The above command requires that the python package manager `pip` is installed.

## Initialization
Finally, you will need to initialize the database.
This can be done by copying a backup sqlite3 file `data.db` into the root directory.
Alternatively,
it's possible to create a new database file through the following at the project root:
```python
import ibp
engine = ibp.db.create_engine()
ibp.models.Base.metadata(bind=engine)
```

# Development
After going through each of the installation steps,
you can run the server in development mode on your local machine by doing the following:
```bash
python -m bottle -b 127.0.0.1:8000 --debug --reload ibp:app
```
By default, this will load the interface on [localhost port 8000](http://localhost:8000).
