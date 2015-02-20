# Persistent Links Script
The persistent_links.py file is a Python script to maintain desired persistent links on a [Free Star*](http://www.va3uv.com/freestar.htm) system.  It leverages the configuration files used by the `g2_link` program.  It is targeted at Python 2.4+, as many of the [Free Star*](http://www.va3uv.com/freestar.htm) systems are running on Centos 5.x, which ships with Python 2.4.

## How To Use
1. Ensure that you have a working version of Python 2 installed (version 2.4+)
2. Place persistent_links.py on the system and ensure it is executable
3. Edit the script to customize the `G2_LINK_DIRECTORY`, `RF_TIMERS`, and `ADMIN` variables as necessary.
4. Add a crontab entry to run the script periodically.  A sample entry:

```
*/5 * * * * /root/g2_link/persistent_links.py >> /var/log/persistent_links.log 2>&1
```

## How To Test
If you would like to run unit tests on the code, these are contained in `persistent_link_tests.py`.  Follow the following steps:

1. Ensure that you have a working version of Python 2 installed (version 2.4+)
2. Place `persistent_link_tests.py` on the system in the same directory as `persistent_links.py` and ensure that the former is *not* executable (nose will not discover tests by default in an executable script).
3. You must have the packages `mock` and `nose` installed for these tests to execute.
4. Run `nosetests persistent_link_tests.py`

## How To Contribute
If you would like to suggest changes to the script, you may create a ticket associated with it.  You may also submit patches using the following process:

1. Ensure you have a github account
2. Submit a ticket, if one does not already exist
3. Fork the repository on Github
4. Make your changes
5. After ensuring PEP8 compliance, please push to your fork
6. Submit a pull request, referencing the ticket associated with it.