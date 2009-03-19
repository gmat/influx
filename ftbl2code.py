#!/usr/bin/env python
# Module for translation of .ftbl file to R or Fortran code

# 2008-12-08 sokol@insa-toulouse.fr : added netan2Rinit()
# 2008-11-25 sokol@insa-toulouse.fr : adapted for reduced cumomer list
# 2008-09-19 sokol@insa-toulouse.fr : initial release
# Copyright 2008 INSA/INRA UMR792, MetaSys
import time;
from tools_ssg import *;
import C13_ftbl;
import copy;
import os;
global DEBUG;

def fwrap(text):
    """Wraps the text in fortran style, i.e. last char at colomn 72 and
    the following lines are prepended with "     &" (five spaces and ampresand)
    """
    return "\n     &".join(text[i:min(i+72,len(text))] for i in xrange(0, len(text), 72));

def netan2Abcumo_f(Al, bl, vcumol, minput, f, fwrv2i, cumo2i, fortfun="fwrv2Abcumo"):
    """
    Transform cumomer linear sytems collection (from ftbl file)
    to a Fortran subroutine code calculating matrix A and vector b
    in A*x=b for a given weight iw (input Fortran parameter)
    Flux vector fl is known from Fortran parameter list

    2008-08-26 sokol
    """
    f.write("""
C************************************************************************
C Define subroutine for cumomer matrix A for a given weight iw
C NB: This is an automatically generated code. Don't edit
C Generated by
C %(cmd)s
C at %(date)s
C Copyright Metasys, INSA/INRA UMR 792, Toulouse, France.
C
C************************************************************************


      SUBROUTINE %(fortfun)s(fl, nf, x, nx, iw, n, A, b)

      IMPLICIT NONE
C-------------------------------------------------------------------------
C Calculate dense matrix for system of linear equations A*x=b
C for cumomer vector x of a given weight iw.
C Input:
C fl (double): array of forward-reverse fluxes 
C nf (int): dimension of previous array
C x (double): array of lighter cumomer
C nx (int): x dimension
C iw (int): weight for which the matrix should be calculated
C n (int): A dimension (n x n)
C Output:
C A (double): array(n,n) representing the system matrix.
C b (double): array(n) representing the system rhs.
      INTEGER            nf
      INTEGER            nx
      INTEGER            iw
      INTEGER            n
      DOUBLE PRECISION   fl(nf)
      DOUBLE PRECISION   x(nx)
      DOUBLE PRECISION   A(n,n)
      DOUBLE PRECISION   b(n)
      
C      write(0,*) "%(fortfun)s: start", nf, nx, iw, n
    """%{
    "cmd": join(" ", sys.argv),
    "date": time.ctime(),
    "fortfun": fortfun,
    });
    for (iwl,A) in enumerate(Al):
        w=iwl+1;
        cumos=vcumol[iwl];
        ncumo=len(cumos);
        #d=[c for c in netan['cumo_sys']['A'][w-1] if not c in cumos]
        if ncumo != len(A):
            raise "wrongCumomerNumber";
        #metab_paths=netan['metab_paths']; # ordered by pathways
        f.write("""
      if (iw .EQ. %(iw)d) then
C        matrix definition
C        cumos: %(cumos)s
"""%    {
        "iw": w,
        "cumos": join(", ", cumos),
        });
        # run through the matrix
        for icol in xrange(ncumo):
            for irow in xrange(ncumo):
                sign="-" if (irow != icol) else "";
                term=join('+', trd(A[cumos[irow]].get(cumos[icol],[]), fwrv2i, 'fl(', ')', None));
                if (not term):
                    continue;
                code="         A(%(ir)d,%(ic)d)=%(sign)s(%(term)s)\n" % {
                "ir": irow+1,
                "ic": icol+1,
                "sign": sign,
                "term": term,
                };
                f.write(fwrap(code));
        # run through the rhs
        f.write("""
C        right hand side definition
%(b)s
      endif
""" %   {
        "b": (
        join("\n", (
        fwrap("         b("+str(i+1)+")="+join("+", (
        ("fl("+str(fwrv2i[flux])+")*("
            if cumo.split(':')[0] not in minput else '') +
        joint("+", [
        join("*", trd(lst, cumo2i, "x(", ")", None))
        for (imetab,lst) in dlst.iteritems()
        ])+(")" if cumo.split(":")[0] not in minput else "")
        for (flux,dlst) in bl[iwl].get(cumo,{}).iteritems()
        ), a="0."))
        for (i,cumo) in enumerate(cumos)
        )
        )
        )
        });
    f.write("""
      RETURN
      END SUBROUTINE %(fortfun)s
"""%{"fortfun": fortfun});
def netan2Rinit(netan, org, f, ff):
    global DEBUG;
    """netan2Rinit(netan, org, f, ff)
    Write R code for initialization of all variables before
    cumomer system resolution by khi2 minimization.
    netan is a collection of parsed ftbl information
    f is R code output pointer
    ff is fortran code output pointer
    Return a dictionnary with some python variables:
        "measures": measures,
        "o_mcumos": o_mcumos,
        "cumo2i": cumo2i,
        ...
    """
    # Important python variables:
    # Collections:
    #    netan - (dict) ftbl structured content;
    #    tflcnx - (3-tuple[reac,["d"|"f"|"c"], ["net"|"xch"]] list)- total flux
    #    collection;
    #    measures - (dict) exp data;
    #    rAb - (list) reduced linear systems A*x_cumo=b by weight;
    #    scale - unique scale names;
    #    nrow - counts scale names;
    #    o_sc - ordered scale names;
    #    o_meas - ordered measure types;
    # org - (str) prefix of .ftbl  file like "PPP"
    # File names (str):
    #    n_ftbl (descriptor f_ftbl);
    #    n_opt (R code) (f);
    #    n_fort (fortran code) (ff);
    # Counts: no_fln, no_flx, no_fl (dependent fluxes: net, xch, total),
    #         no_ffn, no_ffx (free fluxes)
    # Index translators:
    #    fwrv2i - flux names to index in R:fwrv;
    #    cumo2i - cumomer names to index in R:x;
    #    ir2isc - mapping measure rows indexes on scale index isc[meas]=ir2isc[meas][ir]
    # Vector names:
    #    cumos (list) - names of R:x;
    #    o_mcumos - cumomers involved in measures;

    # Important R variables:
    # Scalars:
    #    no_w, no_cumos, no_fln, no_flx, no_fl (dependent or unknown fluxes),
    #    no_ffn, no_ffx, no_ff (free fluxes),
    #    no_fcn, no_fcx, no_fc (constrained fluxes),
    #    no_ineq, no_param, no_fmn
    # Name vectors:
    #    nm_cumo, nm_fwrv, nm_flcnx, nm_fln, nm_flx, nm_fl, nm_par,
    #    nm_ffn, nm_ffx,
    #    nm_fcn, nm_fcx,
    #    nm_mcumo, nm_fmn
    # Numeric vectors:
    #    fwrv - all fluxes (fwd+rev);
    #    x - all cumomers (weight1+weight2+...);
    #    param - free flux net, free flux xch, scale label, scale mass, scale peak
    #    fcn, fcx, fc,
    #    bp - helps to construct the rhs of flux system
    #    flcnx - complete flux vector (constr+net+xch)
    #    bc - helps to construct flcnx
    #    li - inequality vector (mi%*%flcnx>=li)
    #    ir2isc - measur row to scale vector replicator
    #    ci - inequalities for param use (ui%*%param-ci>=0)
    #    measvec,
    #    measinvvar,
    #    imeas,
    #    fmn
    # Matrices:
    #    Afl, qrAfl, invAfl,
    #    p2bfl - helps to construct the rhs of flux system
    #    mf, md - help to construct flcnx
    #    mi - inequality matrix (ftbl content)
    #    ui - inequality matrix (ready for param use)
    #    measmat - measmat*(x[imeas];1)=vec of simulated not-yet-scaled measures
    # Functions:
    #    param2fl_x - translate param to flux and cumomer vector (initial approximation)
    #    cumo_cost - cost function (khi2)
    #    cumo_grad - finite difference gradient
    #    flcnx2fwrv - produce fw-rv fluxes from flcnx

    # Main steps:
    #    python var init;
    #    R init;
    #    R function flcnx2fwrv();
    #    python measures, cumos, cumo2i;
    #    fortran code for cumomer systems A*x=b;
    #    R var init;
    #    R Afl, qr(Afl), invAfl;
    #    R param (without scale factors);
    #    R constrained fluxes
    #    R p2bfl, bp
    #    R mf, md, bc
    #    R mi, li
    #    python measure matrix, vector and vars
    #    R ui, ci
    #    R measure matrix, vector, vars
    #    R flux measures

    # header
    f.write("# This is an automatically generated R code. Don't edit.\n");
    f.write("# Generated by \n# "+join(" ", sys.argv)+"\n# at "+time.ctime()+".\n");
    f.write("""
# Copyright Metasys, INSA/INRA UMR 792, Toulouse, France.
""");
    #if DEBUG:
    #    pdb.set_trace();
    res={};
    netan2R_fl(netan, org, f, ff);
    d=netan2R_rcumo(netan, org, f, ff);
    res.update(d);
    d=netan2R_cumo(netan, org, f, ff);
    res.update(d);
    d=netan2R_meas(netan, org, f, ff);
    res.update(d);
    netan2R_ineq(netan, org, f, ff);
    return res;

def netan2R_fl(netan, org, f, ff):
    """netan2R_fl(netan, org, f, ff)
    generate R code for flux part
    for more details cf. netan2Rinit()
    """
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

    f.write("""
# get runtime arguments
opts=commandArgs();
# profile or not profile?
prof=(length(which(opts=="--prof")) > 0);

# is there method for sensitivity matrix calculation?
sensitive=which(opts=="--sens");
if (length(sensitive)) {
   sensitive=opts[sensitive[1]+1];
} else {
   sensitive=""; # no sensitivity matrix calculation
}

# R profiling
if (prof) {
   Rprof("%(proffile)s");
}

# minimisation method
validmethods=list("BFGS", "Nelder-Mead");
method=which(opts=="--meth");
if (length(method)) {
   method=opts[method[1]+1];
}
if (is.na(method) || !length(which(method==validmethods))) {
   # set default method
   method="BFGS";
}

# get some tools
source("tools_ssg.R");
source("opt_cumo_tools.R");
#require(matrid, lib.loc="/home/sokol/R/lib");
dyn.load("%(sofile)s")

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
   fwrv=c(xch-pmin(-net,0),xch-pmin(net,0));
   if (DEBUG) {
      n=length(fwrv);
      nms=paste(nm_fwrv,c(rep("fwd", n/2),rep("rev", n/2)),sep="_");
      library(MASS);
      write.matrix(cbind(1:n,nms,fwrv), file="dbg_fwrv.txt", sep="\\t");
   }
   return(fwrv);
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
        "proffile": os.path.basename(f.name)[:-1]+"Rprof",
        "sofile": os.path.basename(ff.name)[:-1]+"so",
    });
    f.write("""
# fwd-rev flux names
nm_fwrv=c(%(nm_fwrv)s);

# net-xch flux names
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
dimnames(Afl)=list(c(), nm_fl);
if (DEBUG) {
   library(MASS);
   write.matrix(Afl, file="dbg_Afl.txt", sep="\t");
}

qrAfl=qr(Afl);

# make sure that free params choice leads to not singular matrix
if (qrAfl$rank != no_fl) {
   print(Afl);
   print(nm_fl);
   stop("Flux matrix is singular. You have to change your choice of free fluxes in the '%(n_ftbl)s' file");
}

# inverse flux matrix
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
nm_par=c(nm_par, paste(nm_ffn,".net",sep=""));
# free xch fluxes
no_ffx=%(no_ffx)d;
nm_ffx=c(%(nm_ffx)s);
# starting values for iterations
param=c(param, c(%(ffx)s));
nm_par=c(nm_par, paste(nm_ffx,".xch",sep=""));

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
    "n_ftbl": org+".ftbl",
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
    netan["fwrv2i"]=fwrv2i;
    netan["tflcnx"]=tflcnx;

def netan2R_meas(netan, org, f, ff):
    """netan2R_meas(netan, org, f, ff)
    generate code for measure treatment
    """
    # prepare python measures
    if "measures" not in netan:
        measures=dict();
        for meas in ("label", "mass", "peak"):
            measures[meas]=eval("C13_ftbl.%s_meas2matrix_vec_dev(netan)"%meas);
        netan["measures"]=measures;
    measures=netan["measures"];
    #aff("got measures", measures);
    # get scaling factors and their indexes, measure matrices, and measured cumomer value vector
    scale={"label": {}, "mass": {}, "peak": {}}; # for unique scale names
    nrow={"label": {}, "mass": {}, "peak": {}}; # for counting scale names
    o_sc={"label": {}, "mass": {}, "peak": {}}; # for ordered unique scale names
    o_meas=measures.keys(); # ordered measure types
    o_meas.sort();

    if DEBUG:
        pdb.set_trace();

    ir2isc={"label": [], "mass": [], "peak": []}; # for mapping measure rows indexes on scale index
    # we want to use it in python like isc[meas]=ir2isc[meas][ir]
    for meas in o_meas:
        # get unique scaling factors
        # and count rows in each group
        # row["scale"] is "metab;group"
        for (i,row) in enumerate(measures[meas]["mat"]):
            scale[meas][row["scale"]]=0.;
            nrow[meas][row["scale"]]=nrow[meas].get(row["scale"],0.)+1;
        # remove groups having only one measure in them
        for (k,n) in list(nrow[meas].iteritems()):
            if n<2:
                del(scale[meas][k]);
        # order scaling factor
        o_sc[meas]=scale[meas].keys();
        o_sc[meas].sort();
        # map a measure rows (card:n) on corresponding scaling factor (card:1)
        # if a row has not scale factor it is scaled with factor 1
        # vector having scaling parameters is formed like
        # c(1,param);
        ir2isc[meas]=[-1]*len(measures[meas]["mat"]);
        for (i,row) in enumerate(measures[meas]["mat"]):
            if row["scale"] in scale[meas]:
                ir2isc[meas][i]=o_sc[meas].index(row["scale"]);

        # measured value vector is in measures[meas]["vec"]
        # measured dev vector is in measures[meas]["dev"]

    if DEBUG:
        pdb.set_trace();

    # create R equivalent structures with indices for scaling
    f.write("\n# make place for scaling factors\n");
    for meas in o_meas:
        if not o_sc[meas]:
            continue;
        f.write("""
# %(meas)s
# initial values for scales are set later
param=c(param,%(sc)s);
nm_par=c(nm_par,c(%(sc_names)s));
""" % {
        "meas": meas,
        "sc": join(", ", (scale[meas][sc] for sc in o_sc[meas])),
        "sc_names": join(", ", o_sc[meas], '"'+meas+';', '"'),
        });

    f.write("""
no_param=length(param);
# indices mapping from scaling to measure matrix row
# c(1,par)[ir2isc] replicates scale parameters
# for corresponding rows of measure matrix
ir2isc=numeric(0);
""");
    base_isc=1;
    for meas in o_meas:
        f.write("""
# %(meas)s
ir2isc=c(ir2isc,c(%(ir2isc)s));
""" % {
        "nsc_meas": len(scale[meas]),
        "meas": meas,
        "sc_names": join(", ", o_sc[meas], '"', '"'),
        "ir2isc": join(", ", ((str(ir2isc[meas][ir]+base_isc) if ir2isc[meas][ir]>=0 else -1)
            for ir in xrange(len(ir2isc[meas]))))
        });
        base_isc=base_isc+len(scale[meas]);

    f.write("""
# shift indices by no_ff+1
ir2isc[ir2isc>0]=ir2isc[ir2isc>0]+no_ff+1;
ir2isc[ir2isc<=0]=1;
""");
    # get the full dict of non zero cumomers involved in measures
    # cumo=metab:icumo where icumo is in [1;2^Clen]
    if DEBUG:
        pdb.set_trace();
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
# measmat*(x[imeas];1) or measmat*(xr[irmeas];1)vec of simulated not-yet-scaled measures
# where imeas is the R-index of involved in measures cumomers
# all but 0. Coefficients of 0-cumomers, by defenition equal to 1,
# are all regrouped in the last matrix column.
measmat=matrix(0., 0, %(ncol)d);
measvec=numeric(0);
measinvvar=numeric(0);
imeas=c(%(imeas)s);
irmeas=c(%(irmeas)s);
nm_mcumo=c(%(mcumos)s);
"""%{
    "nrow": len([measures[meas]["vec"] for meas in measures]),
    "ncol": (no_mcumo+1),
    "imeas": join(", ", trd(o_mcumos,netan["cumo2i"],a="")),
    "irmeas": join(", ", trd(o_mcumos,netan["rcumo2i"],a="")),
    "mcumos": join(", ", o_mcumos, '"', '"'),
    });

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
"""%{
        "vec": join(", ", measures[meas]["vec"]),
        "invvar": join(", ", (1./(dev*dev) for dev in measures[meas]["dev"]))
        });

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
    "ifmn": join(", ", (1+netan["vflux_compl"]["net2i"][fl]
        for fl in netan["vflux_meas"]["net"])),
    });
    return {
        "o_meas": o_meas,
        "measures": measures,
        "o_mcumos": o_mcumos,
        "imcumo2i": imcumo2i,
    };

def netan2R_rcumo(netan, org, f, ff):
    # prepare reduced python systems
    rAb=C13_ftbl.rcumo_sys(netan);
    # full matrix is rAb=netan["cumo_sys"]

    # prune ordered cumomer list in reverse order
    # so that deleted item does not change the index
    # for the rest items to prune
    netan["vrcumo"]=copy.deepcopy(netan["vcumo"]);
    for i in xrange(len(netan["vrcumo"]),len(rAb["A"]),-1):
        del(netan["vrcumo"][i-1]);
    for (iw,cumol) in enumerate(netan["vrcumo"]):
        for i in xrange(len(cumol), 0, -1):
            i-=1;
            if cumol[i] not in rAb["A"][iw]:
                #print "prune", i, cumol[i];##
                del(cumol[i]);
    # prepare cumo2i
    # translate cumoname like A:7 to its index in R vector of cumomers
    rcumos=list(valval(netan["vrcumo"]));
    rcumo2i=dict((c,i+1) for (i,c) in enumerate(rcumos));
    # write code for reduced cumomer systems
    netan2Abcumo_f(rAb["A"], rAb["b"],
        netan["vrcumo"], netan["input"], ff, netan["fwrv2i"], rcumo2i, "fwrv2rAbcumo");
    # write R constants and names
    f.write("""
# weight count
no_rw=%(no_rw)d;
# cumomer count by weight;
no_rcumos=c(%(no_rc)s);
# cumo names
nm_rcumo=c(%(nm_rcumo)s);
"""%{
    "no_rw": len(rAb["A"]),
    "no_rc": join(", ", (len(a) for a in rAb["A"])),
    "nm_rcumo": join(", ", valval(netan['vrcumo']), '"', '"'),
});
    netan["rcumo2i"]=rcumo2i;
    return {
        "rcumo2i": rcumo2i,
        "rAb": rAb,
    };

def netan2R_cumo(netan, org, f, ff):
    # prepare cumo2i
    # translate cumoname like A:7 to its index in R vector of cumomers
    cumos=list(valval(netan["vcumo"]));
    cumo2i=dict((c,i+1) for (i,c) in enumerate(cumos));

    # write code for complete cumomer systems
    netan2Abcumo_f(netan["cumo_sys"]["A"], netan["cumo_sys"]["b"],
        netan["vcumo"], netan["input"], ff, netan["fwrv2i"], cumo2i, "fwrv2Abcumo");
    # write R constants and names
    f.write("""
# weight count
no_w=%(no_w)d;

# cumomer count by weight;
no_cumos=c(%(no_c)s);

# cumo names
nm_cumo=c(%(nm_cumo)s);
"""%{
    "no_w": len(netan["cumo_sys"]["A"]),
    "no_c": join(", ", (len(a) for a in netan["cumo_sys"]["A"])),
    "nm_cumo": join(", ", valval(netan['vcumo']), '"', '"'),
});
    netan["cumo2i"]=cumo2i;
    return {
        "cumo2i": cumo2i,
    };

def netan2R_ineq(netan, org, f, ff):
    """netan2R_ineq(netan, org, f, ff)
    generate inequality code
    """
    # ex: netan["flux_inequal"]
    # {'net': [], 'xch': [('0.85', '>=', {'v2': '+1.'})]}
    tflcnx=netan["tflcnx"];
    f.write("""
# prepare mi matrix and li vector
# such that mi%*%flcnx>=li corresponds
# to the inequalities given in ftbl file
mi=matrix(0.,0,no_flcnx);
li=numeric(0);
""");
    
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
    f.write("""
# add standard limits on net >= 0 for not reversible reactions
""");
    for (fli,t,nxi) in tflcnx:
        if nxi=="xch" or fli not in netan["notrev"]:
            continue;
        f.write("""
mi=rbind(mi,c(%(mi)s));
li=c(li,0.);
"""%{
    "mi": join(", ", (
        ("1." if fli==fl and nx=="net" else "0.") for (fl,t,nx) in tflcnx)),
    });

    f.write("no_ineq=NROW(li);\n");
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

