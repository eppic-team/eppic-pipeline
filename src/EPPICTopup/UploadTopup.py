#!/usr/bin/python
'''
Created on Jan 28, 2015

@author: baskaran_k
'''


from time import localtime,strftime
import sys
from re import findall
from commands import getoutput,getstatusoutput
import MySQLdb
from string import atof,atoi
from datetime import date, timedelta


class UploadTopup:

    def __init__(self,offsetday):

        self.mysqluser='eppicweb'
        self.mysqlhost='localhost'
        self.mysqlpasswd=''
        self.eppictoosjar='/home/eppicweb/software/jars/eppic-dbtools.jar'
        self.eppicpath='/home/eppicweb/software/bin/eppic'
        self.eppicconf='/home/eppicweb/.eppic.conf'
        self.pdbrepo="/data/dbs/pdb"
        self.topupDir="/home/eppicweb/topup"
        self.topupDay=date.today() -timedelta(offsetday)
        self.pdbrdate=self.topupDay - timedelta(1)
        self.today=self.topupDay.strftime("%d-%m-%Y")
        self.workDir="%s/%s"%(self.topupDir,self.today)
        self.checkDate()
        self.logfile=open("%s/upload_%s.log"%(self.workDir,self.today),'a')
        self.getUniprotVersion()
        self.uniprot="uniprot_%s"%(self.version)
        self.eppicdb="eppic_%s"%(self.version)
        self.mysqldb=self.eppicdb
        self.statFile="%s/statistics_%s.html"%(self.workDir,self.today)
        self.filesDir="/data/webapps/files_%s"%(self.version)
        self.checkJobs()

    def checkDate(self):
        if self.topupDay!=date.today():
            chk=raw_input("Do you want to proceed the upload part of the topup started on %s [Y/N] :"%(self.topupDay.strftime("%d-%m-%Y")))
            if chk=="Y" or chk=="y" or chk=="yes":
                print "Manual upload started for topup started on %s"%(self.topupDay.strftime("%d-%m-%Y"))
            else:
                print "Manual upload canceled for topup started on %s"%(self.topupDay.strftime("%d-%m-%Y"))
                exit(0)
        chfld=getstatusoutput("ls %s"%(self.workDir))
        if chfld[0]:
            sys.exit(0)
        else:
            chfkd2=getstatusoutput("ls %s/statistics_%s.html"%(self.workDir,self.today))
            if chfkd2[0]==0:
                sys.exit(0)


    def checkJobs(self):
        qstatdump=getoutput('source /var/lib/gridengine/default/common/settings.sh;qstat -u eppicweb -q topup.q')
        qstatparse=findall(r'\s+\d+\s+\S+\s+topup\s+eppicweb\s+\S\s+\S+\s+\S+\s+\S+\s+\d+\s+(\d+)\n|\s+\d+\s+\S+\s+topup\s+eppicweb\s+\S\s+\S+\s+\S+\s+\S+\s+\d+\s+(\d+)',qstatdump)
        if len(qstatparse)>1:
            self.runningJobs=[i[0] for i in qstatparse]
        elif len(qstatparse)==1:
            self.runningJobs=[i[1] for i in qstatparse]
        else:
            self.runningJobs=[]
        self.checkstatfile=getstatusoutput("ls %s"%(self.statFile))
        if len(self.runningJobs)==0 and self.checkstatfile[0]==512: #512 means file not found
            self.writeLog("INFO: No more jobs in qsub and %s file not found"%(self.statFile))
            self.writeLog("INFO: Starting upload process")
            self.runAll()
            self.sendReport()
        elif len(self.runningJobs)!=0:
            if len(self.runningJobs)==1:
                self.writeLog("INFO: %d job running"%(len(self.runningJobs)))
            else:
                self.writeLog("INFO: %d jobs running"%(len(self.runningJobs)))
            self.sendMessage()
        elif self.checkstatfile[0]==0:
            self.writeLog("INFO: statistics file already exists")
            self.sendReport()
        else:
            self.writeLog("ERROR: Something wrong !")
            sys.exit(1)


    def writeLog(self,msg):
        t=strftime("%d-%m-%Y_%H:%M:%S",localtime())
        self.logfile.write("%s\t%s\n"%(t,msg))
        #print "%s\t%s\n"%(t,msg)

    def getUniprotVersion(self):
        universion=getstatusoutput("cat %s | grep LOCAL_UNIPROT_DB_NAME"%(self.eppicconf))
        if universion[0]:
            self.writeLog("ERROR: Can't find uniport version from %s file"%(self.eppicconf))
            sys.exit(1)
        else:
            self.version=universion[1].split("uniprot_")[-1]
            #self.writeLog("INFO: UniProt version : %s"%(self.version))


    def rsyncFolder(self):
        self.writeLog("INFO: synchronizing %s/output/data/divided to %s/divided"%(self.workDir,self.filesDir))
        rsynccmd="rsync -az %s/output/data/divided %s/"%(self.workDir,self.filesDir)
        rsyncstat=getstatusoutput(rsynccmd)
        if rsyncstat[0]:
            self.writeLog("INFO: synchronizing %s/output/data/divided to %s/divided"%(self.workDir,self.filesDir))
            sys.exit(1)
        else:
            self.writeLog("INFO: synchronizing %s/output/data/divided to %s/divided Done!"%(self.workDir,self.filesDir))


    def createSymlink(self):
        newPdblist=open("%s/input/newPDB_%s.list"%(self.workDir,self.today),'r').read().split("\n")[:-1]
        for pdb in newPdblist:
            symlinkcmd="cd %s;ln -s divided/%s/%s"%(self.filesDir,pdb[1:3],pdb)
            ck=getstatusoutput(symlinkcmd)
            if ck[0]:
                self.writeLog("ERROR: can't run %s"%(symlinkcmd))
                sys.exit(1)

    def uploadFiles(self):
        uploadcmd="java -jar %s UploadToDb -D %s  -d %s/ -f %s/input/pdbinput_%s.list -F  > /dev/null"%(self.eppictoosjar,self.eppicdb,self.filesDir,self.workDir,self.today)
        ck=getstatusoutput(uploadcmd)
        if ck[0]:
            self.writeLog("ERROR: Problem in uploading data %s"%(ck[1]))
            sys.exit(1)

    def removeObsolete(self):
        self.deletedEntries=atoi(getoutput("cat %s/input/deletedPDB_%s.list | wc -w"%(self.workDir,self.today)))
        if self.deletedEntries<20:
            delcmd="java -jar %s UploadToDb -D %s -d %s/ -f %s/input/deletedPDB_%s.list -r  > /dev/null"%(self.eppictoosjar,self.eppicdb,self.filesDir,self.workDir,self.today)
            ck=getstatusoutput(delcmd)
            if ck[0]:
                self.writeLog("ERROR: Problem in deleteing obsolete entries %s"%(ck[1]))
                sys.exit(1)
        else:
            sendmail="mail -s \"EPPIC topup warning\"  \"eppic@systemsx.ch\" <<< \"More than 20 obsolete entries found. Please check and delete manually\""
            ck2=getstatusoutput(sendmail)
            if ck2[0]:
                self.writeLog("ERROR: Can't sent mail about more than 20 obsolete entries")
                sys.exit(1)
    def connectDatabase(self):
        #self.writeLog("INFO: Connecting to MySQL database")
        try:
            self.cnx=MySQLdb.connect(user=self.mysqluser,host=self.mysqlhost,passwd=self.mysqlpasswd,db=self.mysqldb)
            self.cursor=self.cnx.cursor()
        except:
            self.writeLog("ERROR:Can't connect to mysql database")
            sys.exit(1)
    def runQuery(self,sqlquery):
        try:
            self.cursor.execute(sqlquery)
            queryout=self.cursor.fetchall()
        except:
            self.writeLog("ERROR: Can't execute '%s'"%(sqlquery))
            queryout=-1
            sys.exit(1)
        return queryout


    def writeStatistics(self):
        new=atof(getoutput("cat %s/input/newPDB_%s.list | wc -w"%(self.workDir,self.today)))
        updated=atof(getoutput("cat %s/input/updatedPDB_%s.list | wc -w"%(self.workDir,self.today)))
        deleted=atof(getoutput("cat %s/input/deletedPDB_%s.list | wc -w"%(self.workDir,self.today)))
        total=new+updated
        PdbCount=atof(getoutput("find  /data/dbs/pdb/data/structures/all/mmCIF/ -name *.cif.gz |  wc -l"))
        self.connectDatabase()
        EppicCount=atof(self.runQuery("select count(*) from Job where length(jobId)=4 and status=\"Finished\"")[0][0])
        EppicCountp=(EppicCount/PdbCount)*100
        InterfaceCount=atof(self.runQuery("select count(*) from InterfaceScore as s inner join Interface as i \
        on i.uid=s.interfaceItem_uid inner join InterfaceCluster as ic on ic.uid=i.interfaceCluster_uid inner join \
        PdbInfo as p on p.uid=ic.pdbInfo_uid inner join Job as j on j.uid=p.job_uid where length(jobId)=4 and s.method=\"eppic\"")[0][0])
        BioCount=atof(self.runQuery("select count(*) from InterfaceScore as s inner join Interface as i on i.uid=s.interfaceItem_uid \
        inner join InterfaceCluster as ic on ic.uid=i.interfaceCluster_uid inner join PdbInfo as p on p.uid=ic.pdbInfo_uid inner join \
        Job as j on j.uid=p.job_uid where length(jobId)=4 and s.method=\"eppic\" and s.callName=\"bio\"")[0][0])
        BioCountp=(BioCount/InterfaceCount)*100
        XtalCount=atof(self.runQuery("select count(*) from InterfaceScore as s inner join Interface as i on i.uid=s.interfaceItem_uid \
        inner join InterfaceCluster as ic on ic.uid=i.interfaceCluster_uid inner join PdbInfo as p on p.uid=ic.pdbInfo_uid inner join \
        Job as j on j.uid=p.job_uid where length(jobId)=4 and s.method=\"eppic\" and s.callName=\"xtal\"")[0][0])
        XtalCountp=(XtalCount/InterfaceCount)*100
        ChainCount=atof(self.runQuery("select count(*) from ChainCluster c inner join PdbInfo as p on p.uid=c.pdbInfo_uid inner join Job as j \
        on j.uid=p.job_uid where length(jobId)=4")[0][0])
        ChainHasUniprot=atof(self.runQuery("select count(*) from ChainCluster c inner join PdbInfo as p on p.uid=c.pdbInfo_uid inner join Job as j \
        on j.uid=p.job_uid where length(jobId)=4 and c.hasUniProtRef")[0][0])
        ChainHasUniprotp=(ChainHasUniprot/ChainCount)*100
        ChainHas10H60P=atof(self.runQuery("select count(*) from ChainCluster c inner join PdbInfo as p on p.uid=c.pdbInfo_uid inner join Job as j on \
        j.uid=p.job_uid where length(jobId)=4 and c.hasUniProtRef and c.seqIdCutoff>0.59 and c.numHomologs>=10")[0][0])
        ChainHas10H60Pp=(ChainHas10H60P/ChainHasUniprot)*100
        ChainHas30H60P=atof(self.runQuery("select count(*) from ChainCluster c inner join PdbInfo as p on p.uid=c.pdbInfo_uid inner join Job as j on \
        j.uid=p.job_uid where length(jobId)=4 and c.hasUniProtRef and c.seqIdCutoff>0.59 and c.numHomologs>=30")[0][0])
        ChainHas30H60Pp=(ChainHas30H60P/ChainHasUniprot)*100
        ChainHas50H60P=atof(self.runQuery("select count(*) from ChainCluster c inner join PdbInfo as p on p.uid=c.pdbInfo_uid inner join Job as j on \
        j.uid=p.job_uid where length(jobId)=4 and c.hasUniProtRef and c.seqIdCutoff>0.59 and c.numHomologs>=50")[0][0])
        ChainHas50H60Pp=(ChainHas50H60P/ChainHasUniprot)*100
        ChainHas10H50P=atof(self.runQuery("select count(*) from ChainCluster c inner join PdbInfo as p on p.uid=c.pdbInfo_uid inner join Job as j on \
        j.uid=p.job_uid where length(jobId)=4 and c.hasUniProtRef and c.seqIdCutoff>0.49 and c.numHomologs>=10")[0][0])
        ChainHas10H50Pp=(ChainHas10H50P/ChainHasUniprot)*100
        ExpStat=self.runQuery("select expMethod,count(*) from PdbInfo as p inner join Job as j on j.uid=p.job_uid \
        where length(jobId)=4 group by p.expMethod order by count(*) desc")
        Top10Area=self.runQuery("select p.pdbCode,p.expMethod,i.interfaceId,i.area from Interface as i inner join \
        InterfaceCluster as ic on ic.uid=i.interfaceCluster_uid inner join PdbInfo as p on p.uid=ic.pdbInfo_uid inner join \
        Job as j on j.uid=p.job_uid where length(jobId)=4 order by i.area desc limit 10")
        Top10Core=self.runQuery("select p.pdbCode,p.expMethod,i.interfaceId,s.score from InterfaceScore as s inner join \
        Interface as i on i.uid=s.interfaceItem_uid inner join InterfaceCluster as ic on ic.uid=i.interfaceCluster_uid inner join \
        PdbInfo as p on p.uid=ic.pdbInfo_uid inner join Job as j on j.uid=p.job_uid where length(jobId)=4 and s.method=\"eppic-gm\" \
        order by s.score desc limit 10")
        Top10inter=self.runQuery("select p.pdbCode,p.expMethod,count(*) from InterfaceScore as s inner join Interface as i on \
        i.uid=s.interfaceItem_uid inner join InterfaceCluster as ic on ic.uid=i.interfaceCluster_uid inner join PdbInfo as p on \
        p.uid=ic.pdbInfo_uid inner join Job as j on j.uid=p.job_uid where length(jobId)=4 and s.method=\"eppic\" group by s.pdbCode \
        order by count(*) desc limit 10")
        Top10eppic=self.runQuery("select p.pdbCode,p.expMethod,i.interfaceId,s.score from InterfaceScore as s inner join Interface as i on \
        i.uid=s.interfaceItem_uid inner join InterfaceCluster as ic on ic.uid=i.interfaceCluster_uid inner join PdbInfo as p on \
        p.uid=ic.pdbInfo_uid inner join Job as j on j.uid=p.job_uid where length(jobId)=4 and s.method=\"eppic-cs\" and s.score is not NULL and \
        s.score > -499 and s.callName!=\"nopred\" order by s.score limit 10")
        Top10Clusters=self.runQuery("select p.pdbCode,p.expMethod,ic.clusterId,ic.numMembers from InterfaceCluster as ic inner join PdbInfo as p on \
        p.uid=ic.pdbInfo_uid inner join Job as j on j.uid=p.job_uid where length(jobId)=4 order by ic.numMembers desc limit 10")
        prev_dat=dict((i.split("\t")[0],i.split("\t")[1]) for i in open("%s/statistics_prev.txt"%(self.workDir),'r').read().split("\n")[:-1])
        fo=open(self.statFile,'w')
        fo.write("<!DOCTYPE html>\n<html>\n")
        fo.write("<head>\n<link rel=\"stylesheet\" type=\"text/css\" href=\"eppic-static.css\">\n<link href='http://fonts.googleapis.com/css?family=Open+Sans:400,700,400italic,700italic' rel='stylesheet' type='text/css'>\n</head>\n")
        fo.write("<body>\n")
        fo.write("\t<script type=\"text/javascript\">\n\t\tfunction reloadPage(url) {\n\t\t\twindow.top.location=url;\n\t\t}\n\t</script>\n")
        fo.write("\t<div class=\"eppic-iframe-content\">\n")
        fo.write("\t<img class=\"eppic-iframe-top-img\" src=\"resources/images/eppic-logo.png\">\n")
        fo.write("\t<div class=\"eppic-statistics\">\n")
        fo.write("\t<h1>EPPIC database statistics as of %s</h1>\n"%(self.today))
        fo.write("\t<h3>Based on UniProt_%s and PDB release of %s</h3>\n"%(self.version,self.pdbrdate.strftime("%d-%m-%Y")))
        fo.write("\t<h4>Values in []: absolute and percentual difference between before and after top-up</h4>\n")
        fo.write("\t<h2>Number of entries</h2>\n")
        fo.write("\t<table>\n")
        fo.write("\t<tr><td class=\"text\">Total number of entries in the <a href=\"http://www.pdb.org/pdb/home/home.do\" target=\"_blank\">PDB</a></td><td class=\"numeric\">%.0f</td><td></td></tr>\n"%(PdbCount))
        fo.write("\t<tr><td class=\"text\">Total number of PDB entries in EPPIC db</td><td class=\"numeric\">%.0f</td><td class=\"numeric\">(%0.2f %%)</td></tr>\n"%(EppicCount,EppicCountp))
        fo.write("\t</table>\n")

        fo.write("\t<h2>Top-up on %s</h2>\n"%(self.today))
        fo.write("\t<table>\n")
        fo.write("\t<tr><td class=\"text\">New PDB entries </td><td class=\"numeric\">%.0f</td></tr>\n"%(new))
        fo.write("\t<tr><td class=\"text\">Updated PDB entries </td><td class=\"numeric\">%.0f</td></tr>\n"%(updated))
        fo.write("\t<tr><td class=\"text\">Deleted PDB entries (obsoleted entries) </td><td class=\"numeric\">%.0f</td></tr>\n"%(deleted))
        fo.write("\t</table>\n")
        InterfaceCountdiff=InterfaceCount-atoi(prev_dat['InterfaceCount'])
        if InterfaceCountdiff<0:
                InterfaceCountdiffc="neg_numeric"
        elif InterfaceCountdiff>0:
                InterfaceCountdiffc="pos_numeric"
        else:
                InterfaceCountdiffc="zero_numeric"
        BioCountdiff=BioCount-atoi(prev_dat['BioCount'])
        if BioCountdiff<0:
                BioCountdiffc="neg_numeric"
        elif BioCountdiff>0:
                BioCountdiffc="pos_numeric"
        else:
                BioCountdiffc="zero_numeric"
        BioCountpdiff=BioCountp-atof(prev_dat['BioCountp'])
        XtalCountdiff=XtalCount-atoi(prev_dat['XtalCount'])
        if XtalCountdiff<0:
                XtalCountdiffc="neg_numeric"
        elif XtalCountdiff>0:
                XtalCountdiffc="pos_numeric"
        else:
                XtalCountdiffc="zero_numeric"
        XtalCountpdiff=XtalCountp-atof(prev_dat['XtalCountp'])
        fo.write("\t<h2>Interface statistics</h2>\n")
        fo.write("\t<table>\n")
        fo.write("\t<tr><td class=\"text\">Total number of interfaces in EPPIC db</td><td class=\"numeric\">%.0f</td><td></td><td class=\"%s\">[%d]</td></tr>\n"%(InterfaceCount,InterfaceCountdiffc,InterfaceCountdiff))
        fo.write("\t<tr><td class=\"text\">Total number of interfaces classified as bio</td><td class=\"numeric\">%.0f</td><td class=\"numeric\">(%0.2f %%)</td><td class=\"%s\">[%d (%0.4f %%)]</td></tr>\n"%(BioCount,BioCountp,BioCountdiffc,BioCountdiff,round(BioCountpdiff,4)))
        fo.write("\t<tr><td class=\"text\">Total number of interfaces classified as xtal</td><td class=\"numeric\">%.0f</td><td class=\"numeric\">(%0.2f %%)</td><td class=\"%s\">[%d (%0.4f %%)]</td></tr>\n"%(XtalCount,XtalCountp,XtalCountdiffc,XtalCountdiff,round(XtalCountpdiff,4)))
        fo.write("\t</table>\n")
        ChainCountdiff=ChainCount-atoi(prev_dat['ChainCount'])
        if ChainCountdiff<0:
                ChainCountdiffc="neg_numeric"
        elif ChainCountdiff>0:
                ChainCountdiffc="pos_numeric"
        else:
                ChainCountdiffc="zero_numeric"
        ChainHasUniprotdiff=ChainHasUniprot-atoi(prev_dat['ChainHasUniprot'])
        if ChainHasUniprotdiff<0:
                ChainHasUniprotdiffc="neg_numeric"
        elif ChainHasUniprotdiff>0:
                ChainHasUniprotdiffc="pos_numeric"
        else:
                ChainHasUniprotdiffc="zero_numeric"
        ChainHasUniprotpdiff=ChainHasUniprotp-atof(prev_dat['ChainHasUniprotp'])
        ChainHas10H50Pdiff=ChainHas10H50P-atoi(prev_dat['ChainHas10H50P'])
        if ChainHas10H50Pdiff<0:
                ChainHas10H50Pdiffc="neg_numeric"
        elif ChainHas10H50Pdiff>0:
                ChainHas10H50Pdiffc="pos_numeric"
        else:
                ChainHas10H50Pdiffc="zero_numeric"
        ChainHas10H50Ppdiff=ChainHas10H50Pp-atof(prev_dat['ChainHas10H50Pp'])
        ChainHas10H60Pdiff=ChainHas10H60P-atoi(prev_dat['ChainHas10H60P'])
        if ChainHas10H60Pdiff<0:
                ChainHas10H60Pdiffc="neg_numeric"
        elif ChainHas10H60Pdiff>0:
                ChainHas10H60Pdiffc="pos_numeric"
        else:
                ChainHas10H60Pdiffc="zero_numeric"
        ChainHas10H60Ppdiff=ChainHas10H60Pp-atof(prev_dat['ChainHas10H60Pp'])
        ChainHas30H60Pdiff=ChainHas30H60P-atoi(prev_dat['ChainHas30H60P'])
        if ChainHas30H60Pdiff<0:
                ChainHas30H60Pdiffc="neg_numeric"
        elif ChainHas30H60Pdiff>0:
                ChainHas30H60Pdiffc="pos_numeric"
        else:
                ChainHas30H60Pdiffc="zero_numeric"
        ChainHas30H60Ppdiff=ChainHas30H60Pp-atof(prev_dat['ChainHas30H60Pp'])
        ChainHas50H60Pdiff=ChainHas50H60P-atoi(prev_dat['ChainHas50H60P'])
        if ChainHas50H60Pdiff<0:
                ChainHas50H60Pdiffc="neg_numeric"
        elif ChainHas50H60Pdiff>0:
                ChainHas50H60Pdiffc="pos_numeric"
        else:
                ChainHas50H60Pdiffc="zero_numeric"
        ChainHas50H60Ppdiff=ChainHas50H60Pp-atof(prev_dat['ChainHas50H60Pp'])
        fo.write("\t<h2>Chain and homolog statistics</h2>\n")
        fo.write("\t<table>\n")
        fo.write("\t<tr><td class=\"text\">Total number of chains in EPPIC db</td><td class=\"numeric\">%.0f</td><td></td><td class=\"%s\">[%d]</td></tr>\n"%(ChainCount,ChainCountdiffc,ChainCountdiff))
        fo.write("\t<tr><td class=\"text\">Total number of chains with UniProt match</td><td class=\"numeric\">%.0f</td><td class=\"numeric\">(%0.2f %%)</td><td class=\"%s\">[%d (%0.4f %%)]</td></tr>\n"%(ChainHasUniprot,ChainHasUniprotp,ChainHasUniprotdiffc,ChainHasUniprotdiff,round(ChainHasUniprotpdiff,4)))
        fo.write("\t<tr><td class=\"text\">Total number of chains having at least 10 homologs with 50%% sequence identity</td><td class=\"numeric\">%.0f</td><td class=\"numeric\">(%0.2f %%)</td><td class=\"%s\">[%d (%0.4f %%)]</td></tr>\n"%(ChainHas10H50P,ChainHas10H50Pp,ChainHas10H50Pdiffc,ChainHas10H50Pdiff,round(ChainHas10H50Ppdiff,4)))
        fo.write("\t<tr><td class=\"text\">Total number of chains having at least 10 homologs with 60%% sequence identity</td><td class=\"numeric\">%.0f</td><td class=\"numeric\">(%0.2f %%)</td><td class=\"%s\">[%d (%0.4f %%)]</td></tr>\n"%(ChainHas10H60P,ChainHas10H60Pp,ChainHas10H60Pdiffc,ChainHas10H60Pdiff,round(ChainHas10H60Ppdiff,4)))
        fo.write("\t<tr><td class=\"text\">Total number of chains having at least 30 homologs with 60%% sequence identity</td><td class=\"numeric\">%.0f</td><td class=\"numeric\">(%0.2f %%)</td><td class=\"%s\">[%d (%0.4f %%)]</td></tr>\n"%(ChainHas30H60P,ChainHas30H60Pp,ChainHas30H60Pdiffc,ChainHas30H60Pdiff,round(ChainHas30H60Ppdiff,4)))
        fo.write("\t<tr><td class=\"text\">Total number of chains having at least 50 homologs with 60%% sequence identity</td><td class=\"numeric\">%.0f</td><td class=\"numeric\">(%0.2f %%)</td><td class=\"%s\">[%d (%0.4f %%)]</td></tr>\n"%(ChainHas50H60P,ChainHas50H60Pp,ChainHas50H60Pdiffc,ChainHas50H60Pdiff,round(ChainHas50H60Ppdiff,4)))
        fo.write("\t</table>\n")
        fo.write("\t<h2>Interface area statistics (Top 10)</h2>\n")
        fo.write("\t<table>\n")
        fo.write("\t<tr><th>PDBId</th><th>Exp.method</th><th class=\"numeric\">InterfaceId</th><th class=\"numeric\">Interface area</th></tr>\n")
        for val in Top10Area:
            fo.write("\t<tr><td class=\"text\"><a href=\"http://www.eppic-web.org/ewui/#id/%s\" onclick=\"reloadPage('http://www.eppic-web.org/ewui/#id/%s');\">%s</a></td><td class=\"text\">%s</td><td class=\"numeric\">%.0f</td><td class=\"numeric\">%0.2f &Aring;<sup>2</sup></td></tr>\n"%(val[0],val[0],val[0],val[1],atof(val[2]),atof(val[3])))
        fo.write("\t</table>\n")
        fo.write("\t<h2>Core residues statistics (Top 10)</h2>\n")
        fo.write("\t<table>\n")
        fo.write("\t<tr><th>PDBId</th><th>Exp.method</th><th class=\"numeric\">InterfaceId</th><th class=\"numeric\">Total no. of core residues</th></tr>\n")
        for val in Top10Core:
                fo.write("\t<tr><td class=\"text\"><a href=\"http://www.eppic-web.org/ewui/#id/%s\" onclick=\"reloadPage('http://www.eppic-web.org/ewui/#id/%s');\">%s</a></td><td class=\"text\">%s</td><td class=\"numeric\">%.0f</td><td class=\"numeric\">%.0f</td></tr>\n"%(val[0],val[0],val[0],val[1],atof(val[2]),atof(val[3])))
        fo.write("\t</table>\n")

        fo.write("\t<h2>Maximum number of interfaces in a single PDB entry (Top 10)</h2>\n")
        fo.write("\t<table>\n")
        fo.write("\t<tr><th>PDBId</th><th>Exp.method</th><th class=\"numeric\">Total no. of Interfaces</th></tr>\n")
        for val in Top10inter:
                fo.write("\t<tr><td class=\"text\"><a href=\"http://www.eppic-web.org/ewui/#id/%s\" onclick=\"reloadPage('http://www.eppic-web.org/ewui/#id/%s');\">%s</a></td><td class=\"text\">%s</td><td class=\"numeric\">%.0f</td></tr>\n"%(val[0],val[0],val[0],val[1],atof(val[2])))
        fo.write("\t</table>\n")
        fo.write("\t<h2>Largest interface clusters in a single PDB entry (Top 10)</h2>\n")
        fo.write("\t<table>\n")
        fo.write("\t<tr><th>PDBId</th><th>Exp.method</th><th class=\"numeric\">ClusterId</th><th class=\"numeric\">Cluster size</th></tr>\n")
        for val in Top10Clusters:
                fo.write("\t<tr><td class=\"text\"><a href=\"http://www.eppic-web.org/ewui/#id/%s\" onclick=\"reloadPage('http://www.eppic-web.org/ewui/#id/%s');\">%s</a></td><td class=\"text\">%s</td><td class=\"numeric\">%.0f</td><td class=\"numeric\">%.0f</td></tr>\n"%(val[0],val[0],val[0],val[1],atof(val[2]),atof(val[3])))
        fo.write("\t</table>\n")

        fo.write("\t<h2>Highly conserved interfaces based on Eppic evolutionary score (Top 10)</h2>\n")
        fo.write("\t<table>\n")
        fo.write("\t<tr><th>PDBId</th><th>Exp.method</th><th class=\"numeric\">InterfaceId</th><th class=\"numeric\">Core-surface score</th></tr>\n")
        for val in Top10eppic:
                fo.write("\t<tr><td class=\"text\"><a href=\"http://www.eppic-web.org/ewui/#id/%s\" onclick=\"reloadPage('http://www.eppic-web.org/ewui/#id/%s');\">%s</a></td><td class=\"text\">%s</td><td class=\"numeric\">%.0f</td><td class=\"numeric\">%0.2f</td></tr>\n"%(val[0],val[0],val[0],val[1],atof(val[2]),atof(val[3])))
        fo.write("\t</table>\n")
        fo.write("\t<h2>Experimental technique statistics</h2>\n")
        fo.write("\t<table>\n")
        for val in ExpStat:
                diffvalue=atof(val[1])-atoi(prev_dat[val[0]])
                diffper=((atof(prev_dat[val[0]])/atof(prev_dat["EppicCount"]))*100)-((atof(val[1])/EppicCount)*100)
                if diffvalue<0:
                        diffc="neg_numeric"
                elif diffvalue>0:
                        diffc="pos_numeric"
                else:
                        diffc="zero_numeric"
                fo.write("\t<tr><td class=\"text\">%s</td><td class=\"numeric\">%.0f</td><td class=\"numeric\">(%0.2f %%)</td><td class=\"%s\">[%d (%0.4f %%)]</td></tr>\n"%(val[0],atof(val[1]),(atof(val[1])/EppicCount)*100,diffc,diffvalue,round(diffper,4)))
        fo.write("\t</table>\n")
        fo.write("\t<h3>For the RCSB PDB statistics page, click <a href=\"http://www.pdb.org/pdb/static.do?p=general_information/pdb_statistics/index.html\" target=\"_blank\">here</a></h3>\n")
        fo.write("</div>\n")
        fo.write("</div>\n")
        fo.write("</body>\n</html>")
        fo.close()
    def sendMessage(self):
        if len(self.runningJobs)==1:
            mailmessage="Job Id %s is still running "%(" ".join(self.runningJobs))
        else:
            mailmessage="Job Ids %s are running "%(" ".join(self.runningJobs))
        msg2=mailmessage+"\nMemory info (GB)\n"+getoutput('free -g')
        #print mailmessage
        mailcmd="mail -s \"EPPIC topup running\" \"eppic@systemsx.ch\" <<< \"%s\""%(msg2)
        #mailcmd="mail -s \"EPPIC topup running\" \"kumaran.baskaran@psi.ch\" <<< \"%s\""%(msg2)
        chkml=getstatusoutput(mailcmd)
        if chkml[0]:
            self.writeLog("ERROR: Can't send status message via mail")
        else:
            self.writeLog("INFO: status message via mail")
    def sendReport(self):
        mailmessage2="All jobs finished successfully. Please see the attachment"
        #mailmessage2="This is a test"
        #print mailmessage
        mailcmd2="mail -s \"EPPIC topup finished\" -a \"%s\" \"eppic@systemsx.ch\" <<< \"%s\""%(self.statFile,mailmessage2)
        #mailcmd2="mail -s \"EPPIC topup finished\" -a \"%s\" \"kumaran.baskaran@psi.ch\" <<< \"%s\""%(self.statFile,mailmessage2)
        cpcmd="cp %s /data/webapps/ewui/statistics.html"%(self.statFile)
        chkcp=getstatusoutput(cpcmd)
        if chkcp[0]:
            self.writeLog("ERROR: Can't copy %s to /data/webapps/ewui/"%(self.statFile))
            sys.exit(1)
        else:
            ckml=getstatusoutput(mailcmd2)
            if ckml[0]:
                self.writeLog("ERROR: Can't send the final report through mail")
                sys.exit(1)
            else:
                self.writeLog("INFO: Finished sucessfully and report sent")





    def runAll(self):
        self.rsyncFolder()
        self.createSymlink()
        self.uploadFiles()
        self.removeObsolete()
        self.writeStatistics()

if __name__=="__main__":
    if len(sys.argv)>1:
        offsetdays=atoi(sys.argv[1])
    else:
        offsetdays=0
    p=UploadTopup(offsetdays)
