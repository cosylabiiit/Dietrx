#!/bin/bash

NAME="dietrx"                                  # Name of the application
DJANGODIR=/home/iiitd/SpiceRx/spicedb             # Django project directory
SOCKFILE=/home/iiitd/SpiceRx/bin/gunicorn.sock  # we will communicte using this unix socket
#USER=hello                                        # the user to run as
#GROUP=webapps                                     # the group to run as
NUM_WORKERS=3                                     # how many worker processes should Gunicorn spawn
DJANGO_SETTINGS_MODULE=spicedb.settings             # which settings file should Django use
DJANGO_WSGI_MODULE=spicedb.wsgi                     # WSGI module name

echo "Starting $NAME as spicedb"

# Activate the virtual environment
cd $DJANGODIR
source activate spicerx
export DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE
export PYTHONPATH=$DJANGODIR:$PYTHONPATH

# Create the run directory if it doesn't exist
RUNDIR=$(dirname $SOCKFILE)
test -d $RUNDIR || mkdir -p $RUNDIR

# Start your Django Unicorn
# Programs meant to be run under supervisor should not daemonize themselves (do not use --daemon)
exec /home/iiitd/miniconda3/envs/spicerx/bin/gunicorn ${DJANGO_WSGI_MODULE}:application \
  --name $NAME \
  --workers $NUM_WORKERS \
  --bind=unix:$SOCKFILE \
  --log-level=debug \
  --log-file=-
