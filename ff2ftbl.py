#!/usr/bin/env python

"""
This program gets free flux and free pool values from kvh file
and put them in a ftbl file.

Names in kvh are like "f.n.FLX" or "f.x.FLX" or "pf:Glc6P"
Names in ftbl are like "FLX" in corresponding NET or XCH section
or like "Glc6P" in METABOLITE_POOLS
If a name in kvh file does not have its equivalent in
ftbl file, it is silently ignored.
Optional comments in the original ftbl after the value of
edited flux or pool are lost.

New content is sent to stdout

usage: ./ff2ftbl.py [-h|--help] f.kvh f.ftbl > new_f.ftbl
or: cat f.kvh | ./ff2ftbl.py - f.ftbl > new_f.ftbl
"""
import sys
import os
import getopt
import re
from math import exp

import kvh
def usage(mes):
    sys.stderr.write(os.linesep.join([mes, __doc__]))

try:
    opts,args=getopt.getopt(sys.argv[1:], "h", ["help"])
except getopt.GetoptError, err:
    #pass
    usage(str(err))
    sys.exit(1)

fullsys=False
DEBUG=False
for o,a in opts:
    if o in ("-h", "--help"):
        usage()
        sys.exit(0)
    else:
        assert False, "unhandled option"
#aff("args", args);##
if len(args) != 2:
    usage("Expecting exactly two arguments. Got %d."%len(args))
    exit(1)
fkvh=args[0]
if fkvh == "-":
   # read from standart input
   fkvh=sys.stdin
ftbl=args[1]

# get free fluxes from kvh
ff=kvh.kvh2dict(fkvh)

# convert strings to floats
ff=dict((k,float(v)) for (k,v) in ff.iteritems())

#print("ff=", ff)
# read ftbl in a list of lines
f=open(ftbl, "rb")
lftbl=f.readlines()
# detect flux definition section in ftbl
ifl=[i for (i,l) in enumerate(lftbl) if re.match("^FLUXES\w*(//.*)*", l)][0]
inet=ifl+[i for (i,l) in enumerate(lftbl[ifl:]) if re.match("\tNET\w*(//.*)*", l)][0]
ixch=inet+[i for (i,l) in enumerate(lftbl[inet:]) if re.match("\tXCH\w*(//.*)*", l)][0]
iend=ixch+[i for (i,l) in enumerate(lftbl[ixch:]) if re.match("[^ \t\r\n/]+", l)][0]
#print(ifl,inet,ixch)

# detect metabolite definition section in ftbl
ipool=[i for (i,l) in enumerate(lftbl) if re.match("^METABOLITE_POOLS\w*(//.*)*", l)][0]

# get metab_scale if any
#try:
#    metab_scale=[float(eval(l.split("\t")[2])) for l in lftbl if l.startswith("\tmetab_scale\t")][0]
#except:
#    metab_scale=1.

# main part
# update values in ftbl
for (fl, v) in ff.iteritems():
    try:
        (fdc, nx, flu)=fl.split(".", 2)
    except:
        try:
            (fdc, flu)=fl.split(":", 2)
            nx=None
        except:
            continue
    #if fdc != "f" and fdc != "pf":
    #    continue;
    if nx == "n":
        # replace the value of net free or dependent flux
        iflu=[i for (i,l) in enumerate(lftbl[inet:ixch]) if l.startswith("\t\t%s\tF\t"%flu) or l.startswith("\t\t%s\tD\t"%flu)]
        if len(iflu)==1:
            iflu=inet+iflu[0]
            #print("iflu=", iflu)
        else:
            continue;
        lftbl[iflu]=re.sub("\t\t[^\t]+\t(.)\t.*", "\t\t%s\t\\1\t%.15g"%(flu, v), lftbl[iflu])
        #print("edited %d=%g"%(iflu,v))
    elif nx == "x":
        # replace the value of xch flux
        iflu=[i for (i,l) in enumerate(lftbl[ixch:iend]) if l.startswith("\t\t%s\tF\t"%flu) or l.startswith("\t\t%s\tD\t"%flu)]
        if len(iflu)==1:
            iflu=ixch+iflu[0]
            #print("iflu=", iflu)
        else:
            continue;
        #lftbl[iflu]="\t\t%s\tF\t%.15g%s"%(flu, abs(v), os.linesep)
        lftbl[iflu]=re.sub("\t\t[^\t]+\t(.)\t.*", "\t\t%s\t\\1\t%.15g"%(flu, v), lftbl[iflu])
    elif fdc == "pf":
        # replace the value of pool
        ipfu=[i for (i,l) in enumerate(lftbl[ipool:]) if l.startswith("\t%s\t-"%flu)]
        if len(ipfu)==1:
            ipfu=ipool+ipfu[0]
            #print("ipfu=", ipfu)
        else:
            continue;
        lftbl[ipfu]="\t%s\t%.15g%s"%(flu, -v, os.linesep)

sys.stdout.write("".join(lftbl))