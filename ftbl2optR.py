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
# after execution a file organism.R will be created.
# If it already exists, it will be silently overwritten.
# The generated R code will use organism_sym.R file (A*x=b for cumomers,
# cf. ftbl2symA.py)
# The system Afl*flnx=bfl is created from ftbl file.
# 2008-07-11 sokol: initial version
# 2009-03-18 sokol: interface homogenization for influx_sim package

# Important python variables:
# Collections:
#    netan - (dict) ftbl structured content;
#    tfallnx - (3-tuple[reac,["d"|"f"|"c"], ["net"|"xch"]] list)- total flux
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
#    n_R (R code) (f);
#    n_fort (fortran code) (ff);
# Counts: nb_fln, nb_flx, nb_fl (dependent fluxes: net, xch, total),
#         nb_ffn, nb_ffx (free fluxes)
# Index translators:
#    fwrv2i - flux names to index in R:fwrv;
#    cumo2i - cumomer names to index in R:x;
#    ir2isc - mapping measure rows indexes on scale index isc[meas]=ir2isc[meas][ir]
# Vector names:
#    cumos (list) - names of R:x;
#    o_mcumos - cumomers involved in measures;

# Important R variables:
# Scalars:
#    nb_w, nb_cumos, nb_fln, nb_flx, nb_fl (dependent or unknown fluxes),
#    nb_ffn, nb_ffx, nb_ff (free fluxes),
#    nb_fcn, nb_fcx, nb_fc (constrained fluxes),
#    nb_ineq, nb_param, nb_fmn
# Name vectors:
#    nm_cumo, nm_fwrv, nm_fallnx, nm_fln, nm_flx, nm_fl, nm_par,
#    nm_ffn, nm_ffx,
#    nm_fcn, nm_fcx,
#    nm_mcumo, nm_fmn
# Numeric vectors:
#    fwrv - all fluxes (fwd+rev);
#    x - all cumomers (weight1+weight2+...);
#    param - free flux net, free flux xch, scale label, scale mass, scale peak
#    fcn, fcx, fc,
#    bp - helps to construct the rhs of flux system
#    fallnx - complete flux vector (constr+net+xch)
#    bc - helps to construct fallnx
#    li - inequality vector (mi%*%fallnx>=li)
#    ir2isc - measur row to scale vector replicator
#    ci - inequalities for param use (ui%*%param-ci>=0)
#    measvec,
#    measinvvar,
#    imeas,
#    fmn
# Matrices:
#    Afl, qrAfl, invAfl,
#    p2bfl - helps to construct the rhs of flux system
#    mf, md - help to construct fallnx
#    mi - inequality matrix (ftbl content)
#    ui - inequality matrix (ready for param use)
#    measmat - measmat*(x[imeas];1)=vec of simulated not-yet-scaled measures
# Functions:
#    param2fl_x - translate param to flux and cumomer vector (initial approximation)
#    cumo_cost - cost function (khi2)
#    cumo_grad - finite difference gradient
#    cumo_gradj - implicit derivative gradient

import sys;
import os;
import time;
import copy;

#sys.path.append("/home/sokol/dev/python");
from tools_ssg import *;
import C13_ftbl;

me=os.path.basename(sys.argv[0]);
def usage():
    sys.stderr.write("usage: "+me+" network_name[.ftbl]\n");

#<--skip in interactive session
if len(sys.argv) < 2:
    usage();
    sys.exit(1);

# set some python constants
org=sys.argv[1];
# cut .ftbl if any
if org[-5:]==".ftbl":
    org=org[-5:];

DEBUG=True if len(sys.argv) > 2 and sys.argv[2] else False;
#-->
#DEBUG=True;
import ftbl2code;
ftbl2code.DEBUG=DEBUG;
#org="ex3";
#org="PPP_exact";
#DEBUG=True;
if DEBUG:
    import pdb;


n_ftbl=org+".ftbl";
n_R=org+".R";
n_fort=org+".f";
f_ftbl=open(n_ftbl, "r");
os.system("chmod u+w '%s' 2>/dev/null"%n_R);
os.system("chmod u+w '%s' 2>/dev/null"%n_fort);
f=open(n_R, "w");
ff=open(n_fort, "w");

# parse ftbl
ftbl=C13_ftbl.ftbl_parse(f_ftbl);
f_ftbl.close();

# analyse network
# reload(C13_ftbl);

netan=C13_ftbl.ftbl_netan(ftbl);

# write initialization part of R code
ftbl2code.netan2Rinit(netan, org, f, ff);

#f.write(
"""
# output flux repartition
cat("Dependent fluxes:\\n");
if (nb_fln) {
   print(paste(nm_fln,"net",sep="_"));
}
if (nb_flx) {
   print(paste(nm_flx,"xch",sep="_"));
}
cat("Free fluxes:\\n");
if (nb_ffn) {
   print(paste(nm_ffn,"net",sep="_"));
}
if (nb_ffx) {
   print(paste(nm_ffx,"xch",sep="_"));
}
cat("Constrained fluxes:\\n");
if (nb_fcn) {
   print(paste(nm_fcn,"net",sep="_"));
}
if (nb_fcx) {
   print(paste(nm_fcx,"xch",sep="_"));
}
"""
f.write("""
# set initial scale values to sum(measvec*simvec/dev**2)/sum(simvec**2/dev**2)
# for corresponding measures
vr=param2fl_x(param, nb_f, nb_rw, nb_rcumos, invAfl, p2bfl, bp, fc, irmeas, measmat, measvec, ir2isc, "fwrv2rAbcumo");
simvec=(measmat%*%c(vr$x[irmeas],1.));
if (DEBUG) {
   cat("initial simvec:\\n");
   print(simvec);
}
if (nb_ff < length(param)) {
   ms=measvec*simvec*measinvvar;
   ss=simvec*simvec*measinvvar;
   for (i in (nb_ff+1):length(param)) {
      im=(ir2isc==(i+1));
      param[i]=sum(ms[im])/sum(ss[im]);
   }
}

# check if initial approximation is feasible
ineq=ui%*%param-ci;
if (!all(ineq > 0)) {
   if (sum(ineq==0.)) {
      cat("The following ", sum(ineq==0.), " ineqalities are on the border:\n", sep="");
      print(ineq[ineq==0.,1]);
      stop("Inequalities on the border, cf. log file.");
   }
   if (sum(ineq<0.)) {
      cat("The following ", sum(ineq<0.), " ineqalities are on not respected:\n", sep="");
      print(ineq[ineq<0.,1]);
      stop("Inequalities violated, cf. log file.");
   }
}
""");

f.write("""
# formated output in kvh file
fkvh=file("%(org)s_res.kvh", "w");
"""%{
    "org": org,
});
# main part: call optimization
f.write("""
# save options of command line
cat("command line\n", file=fkvh);
obj2kvh(opts, "opts", fkvh, ident=1);

# save initial flux and cumomer distribution
cat("initial approximation\n", file=fkvh);
names(param)=nm_par;
obj2kvh(param, "free parameters", fkvh, ident=1);

x=vr$x;
names(x)=nm_rcumo;
obj2kvh(x, "starting cumomer vector", fkvh, ident=1);

fwrv=vr$fwrv;
n=length(fwrv);
names(fwrv)=nm_fwrv;
obj2kvh(fwrv, "starting fwd-rev flux vector", fkvh, ident=1);

f=vr$fallnx;
n=length(f);
names(f)=nm_fallnx;
obj2kvh(f, "starting net-xch flux vector", fkvh, ident=1);

rres=cumo_resid(param, nb_f, nb_rw, nb_rcumos, invAfl, p2bfl, bp, fc, irmeas, measmat, measvec, ir2isc, "fwrv2rAbcumo");
obj2kvh(rres$res, "starting cumomer residuals", fkvh, ident=1);

obj2kvh(rres$fallnx[ifmn]-fmn, "flux residual vector", fkvh, ident=1);

rcost=cumo_cost(param, nb_f, nb_rw, nb_rcumos, invAfl, p2bfl, bp, fc, irmeas, measmat, measvec, measinvvar, ir2isc, fmn, invfmnvar, ifmn, "fwrv2rAbcumo");
obj2kvh(rcost, "starting cost value", fkvh, ident=1);

obj2kvh(Afl, "flux system (Afl)", fkvh, ident=1);
obj2kvh(p2bfl%*%param[1:nb_f$nb_ff]+bp, "flux system (bfl)", fkvh, ident=1);

#cat("mass vector:\\n");
#print_mass(x);

names(param)=nm_par;

if (optimize) {
   # optimize all this
   # few iterations of Nelder-Mead before passing to true method
   #control=list(maxit=50, trace=1);
   #res=constrOptim(param, cumo_cost, grad=cumo_gradj,
   #      ui, ci, mu = 1e-4, control,
   #      method="Nelder-Mead", outer.iterations=10, outer.eps=1e-07,
   #      nb_f, nb_rw, nb_rcumos, invAfl, p2bfl, bp, fc,
   #      irmeas, measmat, measvec, measinvvar, ir2isc, fmn, invfmnvar,
   #      ifmn, "fwrv2rAbcumo", NULL);
   #param=res$par;

   # pass control to the true method
   if (method == "BFGS") {
      control=list(maxit=500, trace=1);
      res=constrOptim(param, cumo_cost, grad=cumo_gradj,
         ui, ci, mu = 1e-4, control,
         method="BFGS", outer.iterations=100, outer.eps=1e-07,
         nb_f, nb_rw, nb_rcumos, invAfl, p2bfl, bp, fc,
         irmeas, measmat, measvec, measinvvar, ir2isc, fmn, invfmnvar, ifmn, "fwrv2rAbcumo");
   } else if (method == "Nelder-Mead") {
      control=list(maxit=1000, trace=1);
      res=constrOptim(param, cumo_cost, grad=cumo_gradj,
         ui, ci, mu = 1e-4, control,
         method="Nelder-Mead", outer.iterations=100, outer.eps=1e-07,
         nb_f, nb_rw, nb_rcumos, invAfl, p2bfl, bp, fc,
         irmeas, measmat, measvec, measinvvar, ir2isc, fmn, invfmnvar, ifmn, "fwrv2rAbcumo");
   } else if (method == "SANN") {
      control=list(maxit=1000, trace=1);
      res=constrOptim(param, cumo_cost, grad=cumo_gradj,
         ui, ci, mu = 1e-4, control,
         method="SANN", outer.iterations=100, outer.eps=1e-07,
         nb_f, nb_rw, nb_rcumos, invAfl, p2bfl, bp, fc,
         irmeas, measmat, measvec, measinvvar, ir2isc, fmn, invfmnvar, ifmn, "fwrv2rAbcumo");
   } else {
      stop(paste("Unknown minimization method '", method, "'", sep=""));
   }
   param=res$par;
   names(param)=nm_par;
""");
f.write("""
   obj2kvh(res, "optimization process informations", fkvh);
}
rres=cumo_resid(param, nb_f, nb_rw, nb_rcumos, invAfl, p2bfl, bp, fc, irmeas, measmat, measvec, ir2isc, "fwrv2rAbcumo");
obj2kvh(rres$res, "cumomer residual vector", fkvh);
obj2kvh(rres$fallnx[ifmn]-fmn, "flux residual vector", fkvh);
names(measvec)=nm_meas;
obj2kvh(measvec, "cumomer measure vector", fkvh);

v=param2fl_x(param, nb_f, nb_w, nb_cumos, invAfl, p2bfl, bp, fc, imeas,
   measmat, measvec, ir2isc, "fwrv2Abcumo", "fj_rhs");
x=v$x;
names(x)=nm_cumo;
o=order(nm_cumo);
obj2kvh(x[o], "cumomer vector", fkvh);

fwrv=v$fwrv;
n=length(fwrv);
names(fwrv)=nm_fwrv;
obj2kvh(fwrv, "fwd-rev flux vector", fkvh);

f=v$fallnx;
n=length(f);
names(f)=nm_fallnx;
obj2kvh(f, "net-xch flux vector", fkvh);

if (sensitive=="grad") {
   # sensitivity analysis
   # sensit=df_i/dm_j (jacobian of solution (f) depending on measures (m)
   # perturb mesures 1 by 1 by factor of 1.+pfact and
   # store soltions as columns in sensit
   pfact=0.1;
   sensit=matrix(0, length(nm_fwrv), 0);
   for (i in 1:length(measvec)) {
      # prepare perturbed measures
      measpert=measvec;
      dv=measvec[i]*pfact;
      measpert[i]=measvec[i]+dv;
      # solve perturbed problem
      if (method == "BFGS") {
         control=list(maxit=500, trace=1)
         res=constrOptim(param, cumo_cost, grad=cumo_gradj,
            ui, ci, mu = 1e-04, control,
            method="BFGS", outer.iterations=10, outer.eps=1e-05,
            nb_f, nb_w, nb_cumos, invAfl, p2bfl, bp, fc,
            imeas, measmat, measpert, measinvvar, ir2isc, fmn, invfmnvar, ifmn);
      } else if (method == "Nelder-Mead") {
         control=list(maxit=1000, trace=1);
         res=constrOptim(param, cumo_cost, grad=cumo_gradj,
            ui, ci, mu = 1e-04, control,
            method="Nelder-Mead", outer.iterations=100, outer.eps=1e-05,
            nb_f, nb_w, nb_cumos, invAfl, p2bfl, bp, fc,
            imeas, measmat, measpert, measinvvar, ir2isc, fmn, invfmnvar, ifmn);
      } else if (method == "SANN") {
         control=list(maxit=10000, trace=1)
         res=constrOptim(param, cumo_cost, grad=cumo_gradj,
            ui, ci, mu = 1e-04, control,
            method="SANN", outer.iterations=100, outer.eps=1e-05,
            nb_f, nb_w, nb_cumos, invAfl, p2bfl, bp, fc,
            imeas, measmat, measpert, measinvvar, ir2isc, fmn, invfmnvar, ifmn);
      } else {
         stop(paste("Unknown minimization method '", method, "'", sep=""));
      }
   #print(dv);
   #print(res);
      # store perturbed solution
      v=param2fl_x(res$par, nb_f, nb_w, nb_cumos, invAfl, p2bfl, bp, fc, imeas, measmat, measpert, ir2isc);
   cat("Perturbed free fluxes:\\n");
   print(res$par);
   cat("Perturbed fluxes:\\n");
   print(v$fwrv);
      sensit=cbind(sensit, (v$fwrv-fwrv)/dv);
   }
   dimnames(sensit)[[1]]=nm_fwrv;
   # SD vector for fluxes
   fl_sd=sqrt((sensit**2)%*%(1./measinvvar));
   #names(fl_sd)=dimnames(sensit)[[1]];

   cat("sensitivity matrix:\\n");
   print(sensit);

   cat("fwd-rev flux Standard Deviation (SD):\\n");
   cat(paste(dimnames(sensit)[[1]], fwrv, rep("+-", length(fwrv)), fl_sd), sep="\\n");
} else if (sensitive=="mo") {
   # Monte-Carlo simulation
   nmc=10; # generated measure sample number
   # random measure generation
   nb_meas=length(measvec);
   meas_mc=matrix(rnorm(nmc*nb_meas, measvec, 1./sqrt(measinvvar)), nb_meas, nmc);
   free_mc=matrix(0, nb_param, 0);
   for (imc in 1:nmc) {
      print(paste("imc=",imc,sep=""));
      # minimization
      if (method == "BFGS") {
         control=list(maxit=500, trace=0);
         res=constrOptim(param, cumo_cost, grad=cumo_gradj,
            ui, ci, mu = 1e-04, control,
            method="BFGS", outer.iterations=10, outer.eps=1e-05,
            nb_f, nb_w, nb_cumos, invAfl, p2bfl, bp, fc,
            imeas, measmat, meas_mc[,imc], measinvvar, ir2isc, fmn, invfmnvar, ifmn);
      } else if (method == "Nelder-Mead" || method == "SANN") {
         control=list(maxit=1000, trace=0);
         res=constrOptim(param, cumo_cost, grad=cumo_gradj,
            ui, ci, mu = 1e-04, control,
            method=method, outer.iterations=100, outer.eps=1e-05,
            nb_f, nb_w, nb_cumos, invAfl, p2bfl, bp, fc,
            imeas, measmat, meas_mc[,imc], measinvvar, ir2isc, fmn, invfmnvar, ifmn);
      } else {
         stop(paste("Unknown minimization method '", method, "'", sep=""));
      }
      # store the solution
      free_mc=cbind(free_mc, res$par);
   }
   dimnames(free_mc)[[1]]=names(param);
} else {
   # Linear simulation by jacobian x_f
   x_f=v$x_f;
   dimnames(x_f)=list(nm_cumo, names(fwrv));
   if (DEBUG) {
      library(numDeriv); # for numerical jacobian
      # numerical simulation
      x_fn=num_jacob(param, nb_f, nb_w, nb_cumos, invAfl, p2bfl, bp, fc, imeas, measmat, measvec, ir2isc, "fwrv2Abcumo")
      dimnames(x_fn)=list(nm_cumo, c("x0", names(fwrv)));
      gr=jacobian(cumo_cost, param, method="Richardson", method.args=list(), nb_f, nb_rw, nb_rcumos, invAfl, p2bfl, bp, fc, irmeas, measmat, measvec, measinvvar, ir2isc, fmn, invfmnvar, ifmn, "fwrv2rAbcumo");
      grn=cumo_grad(param, nb_f, nb_rw, nb_rcumos, invAfl, p2bfl, bp, fc, irmeas, measmat, measvec, measinvvar, ir2isc, fmn, invfmnvar, ifmn, fortfun="fwrv2rAbcumo", fj_rhs=NULL);
      browser();
   }
   # reset fluxes and jacobians according to param
   cost=cumo_cost(param, nb_f, nb_rw, nb_rcumos, invAfl, p2bfl, bp, fc, irmeas, measmat, measvec, measinvvar, ir2isc, fmn, invfmnvar, ifmn, "fwrv2rAbcumo");
   grj=cumo_gradj(param, nb_f, nb_rw, nb_rcumos, invAfl, p2bfl, bp, fc, irmeas, measmat, measvec, measinvvar, ir2isc, fmn, invfmnvar, ifmn, fortfun="fwrv2rAbcumo", fj_rhs="frj_rhs");
   
   # covariance matrix of free fluxes
   invcov=t(jx_f$dfm_dff)%*%(jx_f$dfm_dff*invfmnvar)+
      t(jx_f$dr_dff)%*%(jx_f$dr_dff*measinvvar);
   covff=try(solve(invcov));
   if (inherits(covff, "try-error")) {
      # matrix seems to be singular
      cat("Inverse of covariance matrix is singular => there are unsolved fluxes\\n",
         file=stderr());
      # regularize and inverse
      covff=solve(invcov+diag(1.e-4, nrow(invcov)));
   }
   # standart deviations of free fluxes
   sdff=sqrt(diag(covff));
   cat("stats\n", file=fkvh);
   obj2kvh(covff, "covariance free fluxes", fkvh, ident=1);
   covf=jx_f$df_dff%*%covff%*%t(jx_f$df_dff);
   sdf=sqrt(diag(covf));
   obj2kvh(covf, "covariance all fluxes", fkvh, ident=1);
   obj2kvh(sdff, "SD free fluxes", fkvh, ident=1);
   obj2kvh(sdf, "SD all fluxes", fkvh, ident=1);
   # select best defined flux combinations
   s=svd(covf);
   iord=apply(s$u,2,function(v){o=order(abs(v), decreasing=T); n=which(cumsum(v[o]**2)>=0.95); o[1:n[1]]})
   # lin comb coeff matrix
   l=s$u;
   dimnames(l)=dimnames(covf);
   nm_fvrw=dimnames(l)[[1]];
   nb_fvrw=nrow(s$u);
   comb=rep("", nb_fvrw);
   for (j in 1:nb_fvrw) {
      l[j,]=0;
      cva=s$u[iord[[j]],j];
      cva=cva/cva[1];
      l[j,iord[[j]]]=cva;
      cva=sprintf("%+.3g*", cva);
      cva[cva=="+1*"]="+";
      cva[cva=="-1*"]="-";
      cva[1]="";
      comb[j]=paste(cva, nm_fvrw[iord[[j]]], sep="", collapse="");
   }
   # three columns : val sd cv
   sta_comb=l%*%v$fwrv;
   sta_comb=cbind(sta_comb, sqrt(diag(l%*%covf%*%t(l))));
   sta_comb=cbind(sta_comb, sta_comb[,2]/abs(sta_comb[,1]));
   dimnames(sta_comb)=list(comb, c("val", "sd", "cv"));
   o=order(sta_comb[, "cv"]);
   sta_comb=sta_comb[o,];
   obj2kvh(sta_comb, "best cv for fw-rv linear combinations", fkvh, ident=1);
}
if (prof) {
   Rprof(NULL);
}
close(fkvh);
""");

f.close();
ff.close();
# make output files just readable to avoid later casual edition
os.system("chmod a-w '%s'"%n_R);
os.system("chmod a-w '%s'"%n_fort);
