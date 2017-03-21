#!/usr/bin/python
'''
Created on Jan 28, 2015

@author: baskaran_k
'''

from time import localtime,strftime
import sys
from commands import getstatusoutput
#from re import findall
import MySQLdb
from string import atof
from ftplib import FTP


class TopupEPPIC:

    def __init__(self):
        self.eppicpath='/home/eppicweb/software/bin/eppic'
        self.eppicconf='/home/eppicweb/.eppic.conf'
        self.pdbrepo="/data/dbs/pdb"
        self.topupDir="/home/eppicweb/topup"
        self.today=strftime("%Y-%m-%d",localtime())
        self.workDir="%s/%s"%(self.topupDir,self.today)
        mkd=getstatusoutput("mkdir %s"%(self.workDir))
        if mkd[0]:
            print "ERROR: Can't create %s"%(self.workDir)
            sys.exit(1)
        self.logfile=open("%s/topup_%s.log"%(self.workDir,strftime("%Y-%m-%d",localtime())),'a')
        self.getUniprotVersion()
        self.uniprot="uniprot_%s"%(self.version)
        self.eppicdb="eppic_3_0_%s"%(self.version)
        self.createTopupfolder()
        #filesInRsyncDir=getstatusoutput('ls -tr %s'%(self.pdbrepo))
        #if filesInRsyncDir[0]:
        #    self.writeLog("ERROR: Can't get the latest PDB rsync log file in %s"%(self.pdbrepo))
        #    sys.exit(1)
        #self.rsyncfile="%s/%s"%(self.pdbrepo, filesInRsyncDir[1].split("\n")[-1])

    def getUniprotVersion(self):
        universion=getstatusoutput("cat %s | grep LOCAL_UNIPROT_DB_NAME"%(self.eppicconf))
        if universion[0]:
            self.writeLog("ERROR: Can't find uniport version from %s file"%(self.eppicconf))
            sys.exit(1)
        else:
            self.version=universion[1].split("uniprot_")[-1]
            self.writeLog("INFO: UniProt version : %s"%(self.version))


    def createTopupfolder(self):
        self.inputDir="%s/input"%(self.workDir)
        mkd=getstatusoutput("mkdir %s"%(self.inputDir))
        if mkd[0]:
            self.writeLog("ERROR: Can't create %s"%(self.inputDir))
            sys.exit(1)
        self.outputDir="%s/output"%(self.workDir)
        mkd=getstatusoutput("mkdir %s"%(self.outputDir))
        if mkd[0]:
            self.writeLog("ERROR: Can't create %s"%(self.outputDir))
            sys.exit(1)
        self.logDir="%s/logs"%(self.outputDir)
        mkd=getstatusoutput("mkdir %s"%(self.logDir))
        if mkd[0]:
            self.writeLog("ERROR: Can't create %s"%(self.logDir))
            sys.exit(1)
        mkd=getstatusoutput("mkdir %s/data"%(self.outputDir))
        if mkd[0]:
            self.writeLog("ERROR: Can't create %s/data"%(self.outputDir))
            sys.exit(1)
        mkd=getstatusoutput("mkdir %s/data/all"%(self.outputDir))
        if mkd[0]:
            self.writeLog("ERROR: Can't create %s/data/all"%(self.outputDir))
            sys.exit(1)
        mkd=getstatusoutput("mkdir %s/data/divided"%(self.outputDir))
        if mkd[0]:
            self.writeLog("ERROR: Can't create %s/data/divided"%(self.outputDir))
            sys.exit(1)
        self.qsubDir="%s/qsubscripts"%(self.workDir)
        mkd=getstatusoutput("mkdir %s"%(self.qsubDir))
        if mkd[0]:
            self.writeLog("ERROR: Can't create %s"%(self.qsubDir))
            sys.exit(1)

    def parseInpuListFile(self, inputlistfile):
        self.writeLog("INFO: Getting new list from input list")
        f=open(inputlistfile,'r').readlines()
        self.deletedPDB=[]
        self.newPDB=[x.strip('\n') for x in f]
        self.updatedPDB=[]
        self.writeLog("INFO: %d new,%d updated,%d deleted entries found"%(len(self.newPDB),len(self.updatedPDB),len(self.deletedPDB)))

    def prepareInputs(self):
        self.writeLog("INFO: preparing input lists")
        self.pdbinput="%s/pdbinput_%s.list"%(self.inputDir,self.today)
        fo=open(self.pdbinput,'w')
        fo.write("%s\n"%("\n".join(self.newPDB+self.updatedPDB)))
        fo.close()
        fo=open("%s/newPDB_%s.list"%(self.inputDir,self.today),'w')
        fo.write("%s\n"%("\n".join(self.newPDB)))
        fo.close()
        fo=open("%s/updatedPDB_%s.list"%(self.inputDir,self.today),'w')
        fo.write("%s\n"%("\n".join(self.updatedPDB)))
        fo.close()
        fo=open("%s/deletedPDB_%s.list"%(self.inputDir,self.today),'w')
        fo.write("%s\n"%("\n".join(self.deletedPDB)))
        fo.close()
        self.writeLog("INFO: input lists prepared")

    def writeQsubscript(self):
        self.qsubscript="%s/topup_%s.sh"%(self.qsubDir,self.today)
        fo=open(self.qsubscript,'w')
        fo.write("#!/bin/sh\n\n")
        fo.write("#$ -N topup\n#$ -q topup.q\n#$ -e %s/logs\n#$ -o %s/logs\n#$ -t 1-%d\n#$ -l s_rt=12:00:00,h_rt=12:00:30\n"%(self.outputDir,self.outputDir,len(self.newPDB)+len(self.updatedPDB)))
        fo.write("pdb=`grep -v \"^#\"  %s | sed \"s/\(....\).*/\\1/\" | sed \"${SGE_TASK_ID}q;d\"`\n"%(self.pdbinput))
        fo.write("# Cut the middle letters of pdb code for making directory in divided\n")
        fo.write("mid_pdb=`echo $pdb | awk -F \"\" '{print $2$3}'`\n")
        fo.write("# Check is directory is not present\n")
        fo.write("if [ ! -d %s/data/divided/$mid_pdb ]; then mkdir -p %s/data/divided/$mid_pdb; fi\n"%(self.outputDir,self.outputDir))
        fo.write("if [ ! -d %s/data/divided/$mid_pdb/$pdb ]; then mkdir -p %s/data/divided/$mid_pdb/$pdb; fi\n"%(self.outputDir,self.outputDir))
        fo.write("if [ ! -d %s/data/all ]; then mkdir  %s/data/all; fi\n"%(self.outputDir,self.outputDir))
        fo.write("cd %s/data/all/\n"%(self.outputDir))
        fo.write("ln -s ../divided/$mid_pdb/$pdb $pdb\n")
        fo.write("%s -i $pdb -a 1 -s -o %s/data/divided/$mid_pdb/$pdb -l -w -P -g %s\n"%(self.eppicpath,self.outputDir,self.eppicconf))
        fo.write("cp %s/logs/topup.e${JOB_ID}.${SGE_TASK_ID} %s/data/divided/$mid_pdb/$pdb/$pdb.e\n"%(self.outputDir,self.outputDir))
        fo.write("cp %s/logs/topup.o${JOB_ID}.${SGE_TASK_ID} %s/data/divided/$mid_pdb/$pdb/$pdb.o\n"%(self.outputDir,self.outputDir))
        fo.close()

    def submitJobs(self):
        self.writeLog("INFO: Submitting jobs")
        if (len(self.newPDB)+len(self.updatedPDB))<1000:
            subjob=getstatusoutput("source /var/lib/gridengine/default/common/settings.sh;qsub %s"%(self.qsubscript))
            if subjob[0]:
                self.writeLog("ERROR: Can't submit jobs")
                sys.exit(1)
            else:
                self.writeLog("INFO: Job submitted %s"%(subjob[1]))
                mm="%d new entries\n%d updated entries\n%d deleted deleted entries\n%d jobs submitted successfully"%(len(self.newPDB),len(self.updatedPDB),len(self.deletedPDB),len(self.newPDB)+len(self.updatedPDB))
                self.sendMessage(mm)
        else:
            self.writeLog("WARNING: more than 1000 jobs found.Jobs not submitted. Manually submit %s"%(self.qsubscript))
            mm="more than 1000 jobs found.Jobs not submitted. Manually submit %s"%(self.qsubscript)
            self.sendMessage(mm)

    def writeLog(self,msg):
        t=strftime("%Y-%m-%d_%H:%M:%S",localtime())
        self.logfile.write("%s\t%s\n"%(t,msg))
        #print "%s\t%s\n"%(t,msg)

    def connectDatabase(self):
        self.writeLog("INFO: Connecting to MySQL database")
        try:
            self.cnx=MySQLdb.connect(read_default_file="~/.my.cnf",db=self.eppicdb)
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

    def getPreviousStat(self):
        self.writeLog("INFO: Collecting previous statists")
        self.connectDatabase()
        PdbCount=atof(self.runQuery("select count(*) from Job where length(jobId)=4")[0][0])
        EppicCount=atof(self.runQuery("select count(*) from Job where length(jobId)=4 and status='Finished'")[0][0])
        EppicCountp=(EppicCount/PdbCount)*100
        InterfaceCount=atof(self.runQuery("select count(*) from InterfaceScore as s inner join Interface as i on i.uid=s.interfaceItem_uid inner join \
        InterfaceCluster as ic on ic.uid=i.interfaceCluster_uid inner join PdbInfo as p on p.uid=ic.pdbInfo_uid inner join Job as j on j.uid=p.job_uid \
        where length(jobId)=4 and s.method='eppic'")[0][0])
        BioCount=atof(self.runQuery("select count(*) from InterfaceScore as s inner join Interface as i on i.uid=s.interfaceItem_uid inner join \
        InterfaceCluster as ic on ic.uid=i.interfaceCluster_uid inner join PdbInfo as p on p.uid=ic.pdbInfo_uid inner join Job as j on j.uid=p.job_uid \
        where length(jobId)=4 and s.method=\"eppic\" and s.callName=\"bio\"")[0][0])
        BioCountp=(BioCount/InterfaceCount)*100
        XtalCount=atof(self.runQuery("select count(*) from InterfaceScore as s inner join Interface as i on i.uid=s.interfaceItem_uid inner join \
        InterfaceCluster as ic on ic.uid=i.interfaceCluster_uid inner join PdbInfo as p on p.uid=ic.pdbInfo_uid inner join Job as j on j.uid=p.job_uid \
        where length(jobId)=4 and s.method=\"eppic\" and s.callName=\"xtal\"")[0][0])
        XtalCountp=(XtalCount/InterfaceCount)*100
        ChainCount=atof(self.runQuery("select count(*) from ChainCluster c inner join PdbInfo as p on p.uid=c.pdbInfo_uid inner join \
        Job as j on j.uid=p.job_uid where length(jobId)=4")[0][0])
        ChainHasUniprot=atof(self.runQuery("select count(*) from ChainCluster c inner join PdbInfo as p on p.uid=c.pdbInfo_uid inner join \
        Job as j on j.uid=p.job_uid where length(jobId)=4 and c.hasUniProtRef")[0][0])
        ChainHasUniprotp=(ChainHasUniprot/ChainCount)*100
        ChainHas10H60P=atof(self.runQuery("select count(*) from ChainCluster c inner join PdbInfo as p on p.uid=c.pdbInfo_uid inner join Job as \
        j on j.uid=p.job_uid where length(jobId)=4 and c.hasUniProtRef and c.seqIdCutoff>0.59 and c.numHomologs>=10")[0][0])
        ChainHas10H60Pp=(ChainHas10H60P/ChainHasUniprot)*100
        ChainHas30H60P=atof(self.runQuery("select count(*) from ChainCluster c inner join PdbInfo as p on p.uid=c.pdbInfo_uid inner join Job as j \
        on j.uid=p.job_uid where length(jobId)=4 and c.hasUniProtRef and c.seqIdCutoff>0.59 and c.numHomologs>=30")[0][0])
        ChainHas30H60Pp=(ChainHas30H60P/ChainHasUniprot)*100
        ChainHas50H60P=atof(self.runQuery("select count(*) from ChainCluster c inner join PdbInfo as p on p.uid=c.pdbInfo_uid inner join Job as j on \
        j.uid=p.job_uid where length(jobId)=4 and c.hasUniProtRef and c.seqIdCutoff>0.59 and c.numHomologs>=50")[0][0])
        ChainHas50H60Pp=(ChainHas50H60P/ChainHasUniprot)*100
        ChainHas10H50P=atof(self.runQuery("select count(*) from ChainCluster c inner join PdbInfo as p on p.uid=c.pdbInfo_uid inner join Job as j on \
        j.uid=p.job_uid where length(jobId)=4 and c.hasUniProtRef and c.seqIdCutoff>0.49 and c.numHomologs>=10")[0][0])
        ChainHas10H50Pp=(ChainHas10H50P/ChainHasUniprot)*100
        ExpStat=self.runQuery("select expMethod,count(*) from PdbInfo as p inner join Job as j on j.uid=p.job_uid where length(jobId)=4 group by p.expMethod order by count(*) desc")
        fo=open("%s/statistics_prev.txt"%(self.workDir),'w')
        fo.write("PdbCount\t%d\n"%(PdbCount))
        fo.write("EppicCount\t%d\n"%(EppicCount))
        fo.write("InterfaceCount\t%d\n"%(InterfaceCount))
        fo.write("BioCount\t%d\n"%(BioCount))
        fo.write("BioCountp\t%f\n"%(BioCountp))
        fo.write("XtalCount\t%d\n"%(XtalCount))
        fo.write("XtalCountp\t%f\n"%(XtalCountp))
        fo.write("ChainCount\t%d\n"%(ChainCount))
        fo.write("ChainHasUniprot\t%d\n"%(ChainHasUniprot))
        fo.write("ChainHasUniprotp\t%f\n"%(ChainHasUniprotp))
        fo.write("ChainHas10H50P\t%d\n"%(ChainHas10H50P))
        fo.write("ChainHas10H50Pp\t%f\n"%(ChainHas10H50Pp))
        fo.write("ChainHas10H60P\t%d\n"%(ChainHas10H60P))
        fo.write("ChainHas10H60Pp\t%f\n"%(ChainHas10H60Pp))
        fo.write("ChainHas30H60P\t%d\n"%(ChainHas30H60P))
        fo.write("ChainHas30H60Pp\t%f\n"%(ChainHas30H60Pp))
        fo.write("ChainHas50H60P\t%d\n"%(ChainHas50H60P))
        fo.write("ChainHas50H60Pp\t%f\n"%(ChainHas50H60Pp))
        for ent in ExpStat:
            fo.write("%s\t%d\n"%(ent[0],int(ent[1])))
        fo.close()
        self.writeLog("INFO: previous statistics file written")

    def getSiftsFile(self):
        self.writeLog("INFO: downloading latest SIFTS file")
        cmd="curl -s ftp://ftp.ebi.ac.uk/pub/databases/msd/sifts/text/pdb_chain_uniprot.lst > /data/dbs/uniprot/%s/pdb_chain_uniprot.lst"%(self.uniprot)
        chk=getstatusoutput(cmd)
        if chk[0]:
            self.writeLog("ERROR: Can't download the latest SIFTS file")
            sys.exit(1)
    def sendMessage(self,mailmessage):
        #print mailmessage
        mailcmd="mail -s \"EPPIC topup\" \"eppic@systemsx.ch\" <<< \"%s\""%(mailmessage)
        #mailcmd="mail -s \"EPPIC topup\" \"kumaran.baskaran@psi.ch\" <<< \"%s\""%(mailmessage)
        chk=getstatusoutput(mailcmd)
        if chk[0]:
            self.writeLog("WARNING: Can't send the message through mail")
        else:
            self.writeLog("INFO: message sent through mail")
    def getList(self):
        cnx = MySQLdb.connect(read_default_file="~/.my.cnf",db=self.eppicdb)
        cursor = cnx.cursor()

        query = ("SELECT jobId FROM Job;")

        cursor.execute(query)

        allDbIds=[]

        for (row) in cursor:
            allDbIds.append(row[0])
        cursor.close()
        cnx.close()
        return allDbIds
    def getListFromPdbFtp(self):
        localfilename=self.workDir+"/all_pdb_ids.list"
        file = open(localfilename, 'wb')
        ftpserver="ftp.wwpdb.org"
        ftp = FTP(ftpserver)
        ftp.login()
        filename="pub/pdb/derived_data/pdb_entry_type.txt"
        ftp.retrbinary('RETR %s' % filename, file.write)
        file = open(localfilename, "r")
        allIds=[]
        for line in file:
            allIds.append(line.split("\t")[0])
        return allIds
    def getMissingIds(self):
        """
        Gets all ids from pdb ftp and all ids from our db and finds the diff
        assigning it to self.newPDB
        """
        allDbIds=sorted(self.getList())
        allIds=set(sorted(self.getListFromPdbFtp()))
        diff=list(allIds.difference(allDbIds))
        self.newPDB=diff
        self.allPDB=[]
        self.updatedPDB=[]
        self.deletedPDB=[]
        self.writeLog("INFO: " + len(self.newPDB) + " new, " + len(self.updatedPDB) + " updated, " + len(self.deletedPDB) + " deleted")
    def runAll(self):
        self.getSiftsFile()
        self.prepareInputs()
        self.writeQsubscript()
        self.getPreviousStat()
        self.submitJobs()
if __name__=="__main__":
    p=TopupEPPIC()
    p.getMissingIds()
    p.runAll()
