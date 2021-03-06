
.. _install:

.. highlight:: bash


============
Installation
============

The software was developed on Linux
but can be used both on Linux (or other UNIX, MacOS included) and Windows platforms.

.. note:: The code examples here after are given for Unix shell environment.
 On windows, in DOS environment the syntax is often similar and in
 cygwin or Ubuntu environment (Unix tools on Windows) the syntax is identical
 to the Unix's one.


Installation with ``conda``
---------------------------
If you have Anaconda or Miniconda installed on your system, installation of ``influx_si`` resumes to: ::

  $ conda install influx_si -c conda-forge -c bioconda
  
It installs ``influx_si`` itself as well as all needed dependencies both in Python and in R.

If you are on Windows and you never used python scripts on this mashine before then it might be necessary to run the following command to make python scripts executable. In Anaconda Powershell do: ::

 $ echo '$env:PATHEXT += ";.PY"' >> $PROFILE

and restart Anaconda PowerShell to make the change effective.
  
Installation with ``pip``
-------------------------
If you don't have any version of ``conda`` (neither ``miniconda`` nor ``Anaconda``) but do have a Python and R installed on your system, you can install ``influx_si`` with the following procedure.

Your need a python tool called ``pip`` which manages pure python packages. If it is not present on your sustem, you'll have to install it `first <https://pip.pypa.io/en/stable/installing/>`_ to continue with this method. If you have multiple Pyhton versions installed on your system (e.g. Python2 and Python3) you'll have to use ``pip3`` to install the software in the Python3 univers.

The first step will install only Python part of ``influx_si``: ::

  $ pip3 install influx_si
  
or ::

  $ pip3 install --user influx_si
  
if you wish to install ``influx_si`` not system-wide but only in your own userspace.

To use the software ``influx_si``, you'll need some R dependencies listed bellow. You can try to install them by: ::

  $ influx_s.py --install_rdep

If this procedure fails, you'll have to solve the underlying problem identified from its error messages and rerun the command again.

R dependencies
--------------

As of influx_si version 5.0, user has not to install R dependencies manually from an R session. So they are listed here just for information.

- R-3.4.0 or higher (cf http://www.r-project.org/ or your system packaging solution) + the following packages.
  
  + nnls
  + rmumps (5.2.1-6 or higher)
  + arrApply
  + slam
  + limSolve (optional, needed only for ``--lim`` option)
  + multbxxc
  
.. warning:: As of this writing (September 17, 2014), an R package ``nnls`` distributed in precompiled form on Windows platform, can produce wrong results if a 32 bits version is used on Windows 64 bits. To avoid this, use 64 bit version of R on Windows 64 bits or recompile it by hand. To be sure to use 64 bits version of R, check that the ``Path`` system variable has the R path ending by ``\bin\x64`` and not just by ``\bin``.


Python dependencies
-------------------

As of influx_si version 5.0, user has not to install Python dependencies manually. So they are listed here just for information.

- python 3.0 (or higher) and modules
  + scipy
  + libsbml (optional, needed for ftbl2metxml.py)

.. note:: On some Python distributions (e.g. Anaconda) on Windows platform, the association between ``.py`` files and Python interpreter is made in incomplete way: the file is executed but command line arguments are not passed to Python. To correct this, a user with administrator privileges has to edit register base with ``regedit``. The key ``HKEY_CLASSES_ROOT\py_auto_file\shell\open\command`` must be changed from
  
   .. code-block:: text
   
     "<path_to_your_python_dir>\python.exe" "%1"
  
   to
   
   .. code-block:: text
   
     "<path_to_your_python_dir>\python.exe" "%1" %*


   It may happen (depending on your Windows version) that some other keys (related to Python too) have to be modified in similar way.

********************
Test of installation
********************

Open a shell window and get to your working directory.
Copy distributed test directory to the current directory by running ::

 $ influx_s.py --copy_test
 
then you can get in the newly created directory ``test`` and run some tests ::

 $ cd test
 $ influx_s.py e_coli.ftbl

If everything was correctly installed, you should see in your shell window an
output looking like:

.. code-block:: text

 "/home/sokol/.local/bin/influx_s.py" "e_coli.ftbl"
 code gen: 2019-12-11 16:12:17
 calcul  : 2019-12-11 16:12:17
 end     : 2019-12-11 16:12:22

The meaning of this output is quit simple. First, an R code is generated from FTBL file then it is executed till it ends. Time moments at which these three events occur are reported.

The calculation result will be written in ``e_coli_res.kvh``.
It should be almost identical to the same file in ``ok/`` subdirectory.
On Unix you can do ::

$ diff e_coli_res.kvh ok/e_coli_res.kvh

to see if there is any difference. Some small differences in numerical
values can be ok. They might come from variations in versions of R and
underlying numerical libraries (BLAS, LAPACK and so on).

If something went wrong, check the error messages in ``e_coli.err``,
interpret them, try to figure out why the errors occurred and correct them.

In high throughput context, you can find useful to run ``influx_si`` in parallel on many FTBL files. It can be done just by providing more than one FTBL file in argument. For example, with two of FTBLs provided with the package you can run: ::
 
 $ ../influx_s.py e_coli.ftbl e_coli_growth.ftbl
 

In this case, the output looks sightly different than in one by one run:

.. code-block:: text

  "/home/sokol/.local/bin/influx_s.py" "e_coli" "e_coli_growth"
  e_coli: code gen: 2019-12-11 16:22:27
  e_coli_growth: code gen: 2019-12-11 16:22:27
  //calcul: 2019-12-11 16:22:28
  //end   : 2019-12-11 16:22:31
 
The time moments for code generation is preceded by a short version of FTBL file names. The symbol ``//`` means parallel proceeding. Parallel calculations are launched after all files are proceeded for the code generation.

It is the operating system that dispatches and equilibrates the charge
among available CPUs and cores, not ``influx_si`` who simply launches these processes.

For a quick test of ``influx_i``, you can run in the same directory: ::

  $ influx_i.py e_coli_i

Normal output looks like

.. code-block:: text

  "/home/sokol/.local/bin/influx_i.py" "e_coli_i"
  code gen: 2019-12-11 16:25:38
  calcul  : 2019-12-11 16:25:38
  end     : 2019-12-11 16:25:54

Calculation results are written in ``e_coli_i_res.kvh`` and they can be compared with the same file in the ``ok/`` sub-directory. You can also visually check a generated graphic file ``e_coli_i.pdf`` to see if all simulated label kinetics based on estimated fluxes and metabolite concentrations are close to experimental data.

*****************************
Installation of documentation
*****************************

``influx_si`` is distributed with its documentation. To get it easily accessible from your personnal disk space you can run somewhere in your directory tree: ::

 $ influx_s.py --copy_doc

It will create a sub-directory ``doc`` in the current directory. This sub-directory contains ``influx_si.pdf``, all-in-one documentation file but also an ``html`` subdirectory with the documentation browsable in your prefered navigator.

The both documentation versions are also available on-line: `pdf <https://metasys.insa-toulouse.fr/software/influx/influx_si.pdf>`_  and `html <https://metasys.insa-toulouse.fr/software/influx/doc/>`_.

For a quick reminder of available options, launch ::

$ influx_s.py --help

or ::

$ influx_i.py --help

depending on what context you want to treat: stationary or instationary labeling.

For more detailed documentation read :doc:`User's manual <manual>`.
