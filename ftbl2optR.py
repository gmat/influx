#!/usr/bin/env python
#
# Transform an ftbl to R code solving an optimization of flux analysis
# problem min(S) over \Theta, where S=||Predicted-Observed||^2_\Sigma^2
# and \Theta is a vector of free fluxes (net+xch) and scaling parameters.
# Predicted vector is obtained from cumomer vector x (calculated from
# free fluxes and divided in chunks according to the cumo weight) by
# multiplying it by the measure matrices and scale factor, boths coming
# from ftbl file. Observed values vector xo is extracted from ftbl file.
# it is composed of flux and cumomer measures.
# \Sigma^2, covariance diagonal matrices sigma[flux|mass|label|peak]
# are orginated from ftbl

# usage: ./ftbl2optR.py organism
# where organism is the ftbl informative part of file name
# (before .ftbl), e.g. organism.ftbl
# after execution a file organism_opt.R will be created.
# If it already exists, it will be silently overwritten.
# The generated R code will use organism_sym.R file (A*x=b for cumomers,
# cf. ftbl2symA.py)
# The system Afl*flnx=bfl is created from ftbl file.
# 2008-07-11 sokol

import sys;
import time;

sys.path.append("/home/sokol/dev/python");
from tools_ssg import *;
import C13_ftbl;

me=sys.argv[0];
def usage():
    sys.stderr.write("usage: "+me+" organism");

#<--
if len(sys.argv) != 2:
    usage();
    exit(1);
# set some python constants
org=sys.argv[1];
#-->
#org="ex3";


# function definitions
def netan2Acumo_R(netan, f, fwrv2i):
    """
   # Transform netan collection (from ftbl file)
   # to a R code calculating matrix A
   # in A*x=b for a given weight iw (known in calling R environment)
   # After its execution it will write a code defining
   # Al, Ac, Au which are three diagonals and spA is sparse matrix of the
   # the complete matrix A without three main diagonals stored in Al, Ac, Au.
   # Flux vector fwrv is supposed to be known in R environement

   # 2008-07-25 sokol
   """
    # write R code for matrix A of cumomer balance equations
    f.write("""
   # assign A for the weight iw;
   """);
    #pdb.set_trace();
    for w in xrange(1,netan['Cmax']+1):
        cumos=netan['vcumo'][w-1];
        ncumo=len(cumos);
        #d=[c for c in netan['cumo_sys']['A'][w-1] if not c in cumos]
        A=netan['cumo_sys']['A'][w-1];
        if ncumo != len(A):
            raise "wrongCumomerNumber";
        #metab_paths=netan['metab_paths']; # ordered by pathways
        f.write("""
   if (iw==%(iw)d) {
      Al=Ac=Au=numeric(%(ncumo)d);
      # ... and sparse part of the matrix
      #   spA=Matrix(0., ncumo[[iw]], ncumo[[iw]]);
      spA=matrix(0., %(ncumo)d, %(ncumo)d);
      """ % {
        "iw": w,
        "ncumo": ncumo,
        });
        
        f.write("""
      # central diagonal
      Ac=c(%(Ac)s);
      # lower diagonal (first element is a garbage)
      Al=-c(%(Al)s);
      # upper diagonal (last element is a garbage)
      Au=-c(%(Au)s);

      # sparse part (if any)
      """ % {
        "Ac": join(', ', (join('+', trd(A[cumo][cumo], fwrv2i, 'fl[', ']'))
            for cumo in cumos)),
        "Al": join(', ', (join('+', trd(A[cumos[i]].get(cumos[i-1],[]), fwrv2i, 'fl[', ']'), a='0.')
            for i in xrange(ncumo))),
        "Au": join(', ', (join('+', trd(A[cumos[i]].get(cumos[(i+1)%ncumo],[]), fwrv2i, 'fl[', ']'), a='0.')
            for i in xrange(ncumo))),
        });
        # sparse part
        for icol in xrange(ncumo):
            for irow in xrange(ncumo):
                if (irow >= icol-1 and irow <= icol+1):
                    # skip tridiagonal terms which are already stored elsewhere
                    continue;
                term=join('+', trd(A[cumos[irow]].get(cumos[icol],[]), fwrv2i, 'fl[', ']'));
                if (not term):
                    continue;
                f.write("      spA[%d,%d]=-(%s);\n" % (irow+1,icol+1,term));
        f.write("""
   }
   """);

def netan2bcumo_R(netan, f, fwrv2i, cumo2i):
    """write R code for calculating rhs b of cumomer system for a given weight
    iw (1 based). It is supposed to be defined in the calling R env.
    b is an R vector. fwrv2i and cumo2i are dictionnaries
    helping to find index by name."""
    
    f.write("""
   # right hand side term b for a weight iw
   """);
    for w in xrange(1,netan['Cmax']+1):
        cumos=netan['vcumo'][w-1];
        f.write("""
   if (iw==%(iw)d) {
      b=c(%(b)s);
   }
   """ % {
    "iw": w,
    "b": (
        join(', ', (
        join('+', (('fl['+str(fwrv2i[flux])+']*'
        if cumo.split(':')[0] not in netan['input'] else '') +
        join('*', trd(lst, cumo2i, 'x[', ']'))
        for (flux,lst) in netan["cumo_sys"]["b"][w-1].get(cumo,{}).iteritems()
        ), a='0.') for cumo in cumos
        )
        ))
    });


n_ftbl=org+".ftbl";
n_opt=org+"_opt.R";
f_ftbl=open(n_ftbl, "r");
f=open(n_opt, "w");

# parse ftbl
ftbl=C13_ftbl.ftbl_parse(f_ftbl);
f_ftbl.close();

# analyse network
# reload(C13_ftbl);
netan=C13_ftbl.ftbl_netan(ftbl);

# header
f.write("# This is automatically generated R code. Don't edit.\n");
f.write("# Generated by \n# "+join(" ", sys.argv)+"\n# at "+time.ctime()+".\n");
f.write("""
# Copyright Metasys, INSA/INRA UMR 792, Toulouse, France.
""");
#pdb.set_trace();

# dependent flux counts
no_fln=len(netan['vflux']['net']);
no_flx=len(netan['vflux']['xch']);
no_fl=no_fln+no_flx;

# prepare index translator for free fluxes
# it will be used in bfl expressions where names like flx.net must
# be mapped on respecting parameter index
no_ffn=len(netan['flux_free']['net']);
no_ffx=len(netan['flux_free']['xch']);
ffn2iprm=dict((f+'.net',(i+1))
    for (f,i) in netan['vflux_free']['net2i'].iteritems());
ffx2iprm=dict((f+'.net',(i+1+no_ffn))
    for (f,i) in netan['vflux_free']['xch2i'].iteritems());

# prepare fwrv2i
# translate flx.fwd or flx.rev to index in R:fwrv flux vector
# .fwd part
fwrv2i=dict((fl+".fwd",(i+1))
    for (i,fl) in enumerate(netan["vflux_fwrv"]["fw"]));
# .rev part
fwrv2i.update((fl+".rev",(i+1+len(netan["vflux_fwrv"]["rv"])))
    for (i,fl) in enumerate(netan["vflux_fwrv"]["rv"]));
# make tuple for complete flux vector d,f,c
# (name,"d|f|c","net|xch")
tflcnx=zip(
        netan["vflux"]["net"]+
        netan["vflux_free"]["net"]+
        netan["vflux_constr"]["net"]+
        netan["vflux"]["xch"]+
        netan["vflux_free"]["xch"]+
        netan["vflux_constr"]["xch"],
        ["d"]*len(netan["vflux"]["net"])+
        ["f"]*len(netan["vflux_free"]["net"])+
        ["c"]*len(netan["vflux_constr"]["net"])+
        ["d"]*len(netan["vflux"]["xch"])+
        ["f"]*len(netan["vflux_free"]["xch"])+
        ["c"]*len(netan["vflux_constr"]["xch"]),
        ["net"]*len(netan["vflux"]["net"])+
        ["net"]*len(netan["vflux_free"]["net"])+
        ["net"]*len(netan["vflux_constr"]["net"])+
        ["xch"]*len(netan["vflux"]["xch"])+
        ["xch"]*len(netan["vflux_free"]["xch"])+
        ["xch"]*len(netan["vflux_constr"]["xch"]),
        )

# prepare cumo2i
# translate cumoname like A:7 to its index in R:x vector of cumomers
cumos=list(valval(netan["vcumo"]));
cumo2i=dict((c,i+1) for (i,c) in enumerate(cumos));

f.write("""
# get some tools
source("opt_cumo_tools.R");
require(matrid, lib.loc="/home/sokol/R/lib");

# custom functions
# produce fw-rv fluxes from flcnx
flcnx2fwrv=function(flcnx) {
   n=length(flcnx);
   # extract and reorder in fwrv order
   net=flcnx[c(%(inet2ifwrv)s)];
   xch=flcnx[c(%(ixch2ifwrv)s)];
   # expansion 0;1 -> 0;+inf of xch (second half of flcnx)
   xch=xch/(1-xch);
   # fw=xch-min(-net,0)
   # rv=xch-min(net,0)
   return(c(xch-pmin(-net,0),xch-pmin(net,0)));
}
""" % {
    "inet2ifwrv": join(", ", (1+
    (netan["vflux"]["net2i"][fl] if fl in netan["vflux"]["net2i"]
    else no_fln+netan["vflux_free"]["net2i"][fl] if fl in netan["vflux_free"]["net2i"]
    else no_fln+no_ffn+netan["vflux_constr"]["net2i"][fl])
    for fl in netan["vflux_fwrv"]["fw"])),
    "ixch2ifwrv": join(", ", (1+len(netan["vflux_fwrv"]["fw"])+
    (netan["vflux"]["xch2i"][fl] if fl in netan["vflux"]["xch2i"]
    else no_flx+netan["vflux_free"]["xch2i"][fl] if fl in netan["vflux_free"]["xch2i"]
    else no_flx+no_ffx+netan["vflux_constr"]["xch2i"][fl])
    for fl in netan["vflux_fwrv"]["fw"])),
});

f.write("""
fwrv2Acumo=function(fl, iw) {""");
netan2Acumo_R(netan, f, fwrv2i);
f.write("""
   return(list(Ac=Ac, Al=Al, Au=Au, spA=spA));
}
fwrv_x2bcumo=function(fl, x, iw) {
""");
netan2bcumo_R(netan, f, fwrv2i, cumo2i);
f.write("""
   return(b);
}
""");

f.write("""
# weights count
no_w=%(no_w)d;

# cumo names
nm_cumo=c(%(nm_cumo)s);

# fwd-rev flux names
nm_fwrv=c(%(nm_fwrv)s);

# fwd-rev flux names
nm_flcnx=c(%(nm_flcnx)s);

# initialize the linear system Afl*flnx=bfl (0-weight cumomers)
# unknown net flux names
nm_fln=c(%(nm_fln)s);
no_fln=length(nm_fln);
# unknown xch flux names
nm_flx=c(%(nm_flx)s);
no_flx=length(nm_flx);
nm_fl=c(nm_fln, nm_flx);
no_fl=no_fln+no_flx;
# flux matrix
Afl=t(matrix(c(%(Afl)s), no_fl, no_fl));

qrAfl=qr(Afl);

# make sure that free params choice leads to not singular matrix
if (qrAfl$rank != no_fl) {
   print(Afl);
   print(nm_fl);
   stop("Flux matrix is singular.");
}

# invert flux matrix
invAfl=solve(qrAfl);

# prepare param (\Theta) vector
# order: free flux net, free flux xch, scale label, scale mass, scale peak
param=numeric(0);
nm_par=c();
# free net fluxes
no_ffn=%(no_ffn)d;
nm_ffn=c(%(nm_ffn)s);
# starting values for iterations
param=c(param, c(%(ffn)s));
nm_par=c(nm_par, nm_ffn);
# free xch fluxes
no_ffx=%(no_ffx)d;
nm_ffx=c(%(nm_ffx)s);
# starting values for iterations
param=c(param, c(%(ffx)s));
nm_par=c(nm_par, nm_ffx);

# scaling factors are added to param later

no_ff=no_ffn+no_ffx;

# constrained fluxes
# net
no_fcn=%(no_fcn)d;
nm_fcn=c(%(nm_fcn)s);
fcn=c(%(fcn)s);
# xch
no_fcx=%(no_fcx)d;
nm_fcx=c(%(nm_fcx)s);
fcx=c(%(fcx)s);
fc=c(fcn, fcx);
no_fc=no_fcn+no_fcx;

# total flux vector flcnx dimension
no_flcnx=no_fl+no_ff+no_fc;

# all flux cardinals
no_f=list(no_fln=no_fln, no_flx=no_flx, no_fl=no_fl,
   no_ffn=no_ffn, no_ffx=no_ffx, no_ff=no_ff,
   no_fcn=no_fcn, no_fcx=no_fcx, no_fc=no_fc,
   no_flcnx=no_flcnx);

""" % {
"no_w": netan["Cmax"],
"nm_cumo": join(", ", valval(netan['vcumo']), '"', '"'),
"nm_fwrv": join(", ", netan['vflux_fwrv']["fw"]*2, '"', '"'),
"nm_flcnx": join(", ", (join(".", t) for t in tflcnx), '"', '"'),
"nm_fln": join(", ", netan['vflux']['net'], '"', '"'),
"nm_flx": join(", ", netan['vflux']['xch'], '"', '"'),
"Afl": join(", ", [coef for coef in valval(netan['Afl'])]),
"no_ffn": no_ffn,
"no_ffx": no_ffx,
"nm_ffn": join(", ", netan["vflux_free"]["net"], '"', '"'),
"nm_ffx": join(", ", netan["vflux_free"]["xch"], '"', '"'),
"ffn": join(", ", [netan["flux_free"]["net"][fl]
    for fl in netan["vflux_free"]["net"]]),
"ffx": join(", ", [netan["flux_free"]["xch"][fl]
    for fl in netan["vflux_free"]["xch"]]),
"no_fcn": len(netan["flux_constr"]["net"]),
"no_fcx": len(netan["flux_constr"]["xch"]),
"nm_fcn": join(", ", netan["vflux_constr"]["net"], '"', '"'),
"nm_fcx": join(", ", netan["vflux_constr"]["xch"], '"', '"'),
"fcn": join(", ", [netan["flux_constr"]["net"][fl]
    for fl in netan["vflux_constr"]["net"]]),
"fcx": join(", ", [netan["flux_constr"]["xch"][fl]
    for fl in netan["vflux_constr"]["xch"]]),
});
f.write("""
# prepare p2bfl matrix and bp vector such that p2bfl%*%param[1:no_ff]+bp=bfl
# replace flx.net|xch by corresponding param coefficient
p2bfl=matrix(0., 0, no_ff);
bp=numeric(0);
""");
for item in netan["bfl"]:
    f.write("\
p2bfl=rbind(p2bfl, c(%(row)s));\n\
bp=c(bp,%(bp)s);\n"%{
    "row": join(", ",
    (item.get(fl+suf, "0.") for (fl,suf) in
    zip(netan['vflux_free']['net']+netan['vflux_free']['xch'],
    [".net"]*no_ffn+[".xch"]*no_ffx))),
    "bp": join("+", (str(fl)+("*"+str(val) if val else "") for
         (fl,val) in item.iteritems() if not isstr(fl)),a="0."),
    });

f.write("""
# prepare mf, md matrices and bd vector
# such that mf%*%ff+md%*%fl+bc gives flcnx
# here ff free fluxes (param), and fl are dependent fluxes
# (solution of Afl*fl=bfl)
mf=matrix(0.,0,no_ff);
md=matrix(0.,0,no_fl);
bc=numeric(0);
""");

for tf in tflcnx:
    f.write("""
mf=rbind(mf,c(%(mf)s));
md=rbind(md,c(%(md)s));
bc=c(bc,%(bc)g);
"""%{
"mf": join(", ", (1 if tf==(fl,t,nx) else 0 for (fl,t,nx) in tflcnx if t=="f")),
"md": join(", ", (1 if tf==(fl,t,nx) else 0 for (fl,t,nx) in tflcnx if t=="d")),
"bc": netan["flux_constr"][tf[2]][tf[0]] if tf[1]=="c" else 0.,
});

# ex: netan["flux_inequal"]
# {'net': [], 'xch': [('0.85', '>=', {'v2': '+1.'})]}

f.write("""
# prepare mi matrix and li vector
# such that mi%*%flcnx>=li corresponds
# to the inequalities given in ftbl file
mi=matrix(0.,0,no_flcnx);
li=numeric(0);
""");
#
for (ineq,inx) in zip(
        netan["flux_inequal"]["net"]+
        netan["flux_inequal"]["xch"],
        ["net"]*len(netan["flux_inequal"]["net"])+
        ["xch"]*len(netan["flux_inequal"]["xch"])
        ):
    f.write("""
mi=rbind(mi,c(%(mi)s));
li=c(li,%(li)g);
"""%{
"mi": join(", ", (("" if ineq[1]=="<=" or ineq[1]=="=<" else "-")+
    (ineq[2][fl] if inx==nx and fl in ineq[2] else "0.")
    for (fl,t,nx) in tflcnx)),
"li": float(("" if ineq[1]=="<=" or ineq[1]=="=<" else "-")+str(ineq[0])),
});
f.write("""
# add standard limits on xch 0;1
""");
for (fli,t,nxi) in tflcnx:
    if nxi=="net" or t=="c":
        continue;
    f.write("""
mi=rbind(mi,c(%(mi0)s));
mi=rbind(mi,c(%(mi1)s));
li=c(li,0.);
li=c(li,-1.);
"""%{
"mi0": join(", ", (
    ("1." if fli==fl and nx=="xch" else "0.") for (fl,t,nx) in tflcnx)),
"mi1": join(", ", (
    ("-1." if fli==fl and nx=="xch" else "0.") for (fl,t,nx) in tflcnx)),
});
f.write("no_ineq=NROW(li);\n");

# get scaling factors and their indexes, measure matrices, and measured cumomer value vector
measures={"label": {}, "mass": {}, "peak": {}};
scale=dict(measures); # for unique scale names
o_sc=dict(measures); # for unique scale names
o_meas=measures.keys(); # ordered measure types
o_meas.sort();

ir2isc={"label": [], "mass": [], "peak": []}; # for mapping measure rows indexes on scale index
# we want to use it like isc[meas]=ir2isc[meas][ir]
for meas in o_meas:
    # measures[meas]=list[{scale: , coefs: }]
    measures[meas]=eval("C13_ftbl.%s_meas2matrix_vec_dev(netan)"%meas);
    
    # get unique scaling factors
    # row["scale"] is "metab;group"
    for (i,row) in enumerate(measures[meas]["mat"]):
        scale[meas][row["scale"]]=scale[meas].get(row["scale"],0.)+measures[meas]["vec"][i];
    # order scaling factor
    o_sc[meas]=scale[meas].keys();
    o_sc[meas].sort();
    # map a measure rows (card:n) on corresponding scaling factor (card:1)
    ir2isc[meas]=[0]*len(measures[meas]["mat"]);
    for (i,row) in enumerate(measures[meas]["mat"]):
        ir2isc[meas][i]=o_sc[meas].index(row["scale"]);
    
    # measured value vector is in measures[meas]["vec"]
    # measured dev vector is in measures[meas]["dev"]

# create R equivalent structures with indices for scaling
f.write("\n# make place for scaling factors\n");
for meas in o_meas:
    if not o_sc[meas]:
        continue;
    f.write("""
# %(meas)s
# set initial scales to sum(vec_meas)
param=c(param,%(invvec)s);
nm_par=c(nm_par,c(%(sc_names)s));
""" % {
    "meas": meas,
    "invvec": join(", ", (scale[meas][sc] for sc in o_sc[meas])),
    "sc_names": join(", ", o_sc[meas], '"'+meas+';', '"'),
    });

f.write("""
no_param=length(param);
# indices mapping from scaling to measure matrix row
# par[ir2isc] replicates scale parameters
# for corresponding rows of measure matrix
ir2isc=numeric(0);
""");
base_isc=1;
for meas in o_meas:
    f.write("""
# %(meas)s
ir2isc=c(ir2isc,c(%(ir2isc)s));
""" % {
    "nsc_meas": len(scale[meas]), "meas": meas,
    "sc_names": join(", ", o_sc[meas], '"', '"'),
    "ir2isc": join(", ", (str(ir2isc[meas][ir]+base_isc)
        for ir in xrange(len(ir2isc[meas]))))});
    base_isc=base_isc+len(scale[meas]);

f.write("""
# shift indices by no_ff
ir2isc=ir2isc+no_ff;
""");

f.write("""
# prepare ui matrix and ci vector for optimisation
# ui%*%param-ci>=0
# it is composed of explicite inequalities from ftbl
# and permanent inequalities 0<=xch<=0.9999999 and scale>=0

# constraints such that ui%*%param[1:no_ff]-ci>=0
ui=mi%*%(md%*%invAfl%*%p2bfl+mf);

# complete ui by zero columns corresponding to scale params
ui=cbind(ui, matrix(0., no_ineq, no_param-no_ff));
ci=li-mi%*%(bc+(md%*%invAfl%*%bp));

# complete ui by scales >=0
ui=rbind(ui, cbind(matrix(0, no_param-no_ff, no_ff), diag(1, no_param-no_ff)));
ci=c(ci,rep(0., no_param-no_ff));
""");

# get the full dict of non zero cumomers involved in measures
# cumo=metab:icumo where icumo is in [1;2^Clen]
meas_cumos={};
for meas in o_meas:
    for row in measures[meas]["mat"]:
        metab=row["scale"].split(";")[0];
        meas_cumos.update((metab+":"+str(icumo), "") for icumo in row["coefs"].keys() if icumo != 0);

# order involved cumomers
o_mcumos=meas_cumos.keys();
o_mcumos.sort();
imcumo2i=dict((cumo, i) for (i, cumo) in enumerate(o_mcumos));
no_mcumo=len(o_mcumos);
f.write("""
# make measure matrix
# matrix is "densified" such that
# measmat*(x[imeas];1)=vec of simulated not-yet-scaled measures
# where imeas is the index of involved in measures cumomers
# all but 0. Coefficients of 0-cumomers, by defenition equal to 1,
# they are all regrouped in the last matrix column.
measmat=matrix(0., 0, %(ncol)d);
measvec=numeric(0);
measinvvar=numeric(0);
imeas=c(%(imeas)s);
nm_mcumo=c(%(mcumos)s);
"""%{"nrow": len([measures[meas]["vec"] for meas in measures]),
"ncol": (no_mcumo+1),
"imeas": join(", ", trd(o_mcumos,cumo2i)),
"mcumos": join(", ", o_mcumos, '"', '"')});

# get coeffs in the order above with their corresponding indices from total cumomer vector
measmat=[];
for meas in o_meas:
    f.write("""
# %s
"""%meas);
    for row in measures[meas]["mat"]:
        metab=row["scale"].split(";")[0];
        res=[0]*(no_mcumo+1); # initialize the row to zeros
        for (icumo,coef) in row["coefs"].iteritems():
            col=imcumo2i[metab+":"+str(icumo)] if icumo else no_mcumo;
            res[col]=coef;
        f.write("""measmat=rbind(measmat,c(%(row)s));
"""%{"row": join(", ", res)});
    f.write("""
measvec=c(measvec,c(%(vec)s));
measinvvar=c(measinvvar,c(%(invvar)s));
"""%{"vec": join(", ", measures[meas]["vec"]),
"invvar": join(", ", (1./(dev*dev) for dev in measures[meas]["dev"]))});

f.write("""
# prepare flux measures
no_fmn=%(no_fmn)d;
nm_fmn=c(%(nm_fmn)s);

# measured values
fmn=c(%(fmn)s);

# inverse of variance for flux measures
invfmnvar=c(%(invfmnvar)s);

# indices for measured fluxes
# flcnx[ifmn]=>fmn, here flcnc is complete net|xch flux vector
# combining unknown (dependent), free and constrainded fluxes
ifmn=c(%(ifmn)s);

"""%{
"no_fmn": len(netan["vflux_meas"]["net"]),
"nm_fmn": join(", ", netan["vflux_meas"]["net"], '"', '"'),
"fmn": join(", ", (netan["flux_measured"][fl]["val"]
    for fl in netan["vflux_meas"]["net"])),
"invfmnvar": join(", ", (1./(netan["flux_measured"][fl]["dev"]**2)
    for fl in netan["vflux_meas"]["net"])),
"ifmn": join(", ", (netan["vflux_compl"]["net2i"][fl]
    for fl in netan["vflux_meas"]["net"])),
});


# main part: call optimization
f.write("""
# optimize all this
#res=optim(param, cumo_cost,
#   nfree,Afl,imeas,measmat,measvec,measinvvar,ir2isc,
#   method = "L-BFGS-B",
#)
res=constrOptim(param, cumo_cost, grad=NULL, ui, ci, mu = 1e-04, control=list(trace=0),
   method="Nelder-Mead", outer.iterations=100, outer.eps=1e-05,
   no_f, no_w, invAfl, p2bfl, bp, fc, imeas, measmat, measvec, measinvvar, ir2isc, fmn, invfmnvar, ifmn);

# formated output
cat("outer iteration number:\\n");
print(res$outer.iterations);

cat("calculation counts:\\n");
print(res$counts);

cat("achieved minimum:\\n");
print(res$value);

cat("free parameters:\\n");
param=res$par;
names(param)=nm_par;
print(param);

cat("cumomer vector:\\n");
v=param2fl_x(param, no_f, no_w, invAfl, p2bfl, bp, fc, imeas, measmat, measvec, ir2isc);
x=v$x;
names(x)=nm_cumo;
print(x);
cat("cumomer vector ordered by name:\\n");
o=order(nm_cumo);
print(x[o]);

cat("fwd flux vector:\\n");
f=v$fwrv;
n=length(f);
names(f)=nm_fwrv;
print(f[1:(n/2)]);
cat("rev flux vector:\\n");
print(f[((n/2)+1):n]);
""");

f.close();
