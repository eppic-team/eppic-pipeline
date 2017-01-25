import luigi
from eppic_config import EppicConfig
from pkg_resources import resource_string#, resource_stream, resource_listdir
import pybars as hb
import subprocess
from sgetask import CustomSGEJobTask
from luigi.util import inherits,requires
import logging
import os
from eppicpipeline.luigi.util import IncompleteException

logger = logging.getLogger('luigi-interface')
#config = EppicConfig()


class ExternalFile(luigi.ExternalTask):
    filename = luigi.Parameter()
    def output(self):
        return luigi.LocalTarget(self.filename)

class EppicCli(luigi.Task):
    #input; required
    pdb = luigi.Parameter()
    out = luigi.Parameter(default="{}/data/divided/{{mid2}}/{{pdb}}".format(
        EppicConfig().wui_files)
    )
    log = luigi.Parameter(default="") #Empty for no log
    jar = luigi.Parameter(default=EppicConfig().eppic_cli_jar)
    java = luigi.Parameter(default=EppicConfig().java)

    def requires(self): return {
                "conf":CreateEppicConfig(),
                "jar":ExternalFile(filename=self.jar),
                }

    def outputdir(self):
        return str(self.out).format(mid2=self.pdb[1:3],pdb=self.pdb)
    def output(self):
        outs = {
            "dir":luigi.LocalTarget(self.outputdir()),
            "finished":luigi.LocalTarget("{}/finished".format(self.outputdir()) )
            }
        if self.log:
            outs["log"]=luigi.LocalTarget(self.log)
        return outs

    def run(self):
        super(EppicCli,self).run()
        conf = self.input()["conf"]
        outs = self.output()
        log = outs.get("log") #None if not set

        cmd = [self.java,
            "-Xmx3g","-Xmn1g",
            "-jar",str(self.jar),
            "-i", str(self.pdb),
            "-o", str(self.outputdir()),
            "-a","1", #threads
            "-w", #webui.dat
            "-g",conf.eppic_cli_conf_file,
            "-l", #pymol images
            #"-s", #entropy scores
            "-P", #assembly diagrams
            "-p", #interface coordinates
        ]
        rtn = -1
        if log is not None:
            with self.output()["log"].open('w') as out:
                out.write("CMD: "+" ".join(cmd))
                out.flush()
                rtn = subprocess.call(cmd,stdout=out,stderr=subprocess.STDOUT)
        else:
            rtn = subprocess.call(cmd)
        if rtn > 0:
            raise IncompleteException("Non-zero return value (%d) from %s"%(rtn," ".join(cmd)))
        if not self.complete():
            raise IncompleteException("Some outputs were not generated")


class CreateEppicConfig(luigi.Task):
    eppic_cli_conf_file = luigi.Parameter(default=EppicConfig().eppic_cli_conf_file)

    def output(self):
        return luigi.LocalTarget(self.eppic_cli_conf_file)

    def run(self):
        conf = resource_string(__name__, 'eppic.conf.hbs')
        compiler = hb.Compiler()
        # pybars seems to accept only strings (v0.0.4)
        template = compiler.compile(unicode(conf))
        confstr = template(EppicConfig())
        # Write to output
        with self.output().open('w') as out:
            if type(confstr) == hb.strlist:
                for s in confstr:
                    out.write(s)
            else:
                out.write(confstr)

# Note that this superclass order is required
@inherits(EppicCli)
class SGEEppicCli(CustomSGEJobTask):
    def requires(self):
        return {
                "conf":CreateEppicConfig(),
                "jar":ExternalFile(filename=self.jar),
                }

    def outputdir(self):
        return str(self.out).format(mid2=self.pdb[1:3],pdb=self.pdb)
    def output(self):
        return {
            "log":luigi.LocalTarget(self.log) if self.log is not None else None,
            "dir":luigi.LocalTarget(self.outputdir()),
            "finished":luigi.LocalTarget("{}/finished".format(self.outputdir()) )
            }

    def work(self):
        conf = self.input()["conf"]
        outs = self.output()
        log = outs["log"]

        dirname = os.path.dirname(self.outputdir())
        if not os.path.exists(dirname):
            try:
                os.makedirs(dirname)
            except OSError as err:
                if not os.path.exists(dirname):
                    raise err
                else:
                    logger.warn("Concurrent creation of %s",dirname)

        cmd = [self.java,
            "-Xmx3g","-Xmn1g",
            "-jar",str(self.jar),
            "-i", str(self.pdb),
            "-o", str(self.outputdir()),
            "-a","1", #threads
            "-w", #webui.dat
            "-g",conf.open().name, #Is there a way to get the path without opening it?
            "-l", #pymol images
            #"-s", #entropy scores
            "-P", #assembly diagrams
            "-p", #interface coordinates
        ]
        rtn = -1
        if log is not None:
            with log.open('w') as out:
                out.write("CMD: "+" ".join(cmd))
                out.flush()
                rtn = subprocess.call(cmd,stdout=out,stderr=subprocess.STDOUT)
        else:
            rtn = subprocess.call(cmd)
        if rtn > 0:
            raise IncompleteException("Non-zero return value (%d) from %s"%(rtn," ".join(cmd)))
        if not self.complete():
            raise IncompleteException("Some outputs were not generated")

class EppicList(luigi.WrapperTask):
    input_list = luigi.Parameter(description="File containing a list of PDB IDs to run")

    wui_files = luigi.Parameter(description="EPPIC output files root dir", default=EppicConfig().wui_files)

    def requires(self):
        # Require the input
        infile = ExternalFile(filename=self.input_list)
        yield infile

        # Dynamically generate more requirements from the input
        if infile is not None and infile.complete():
            with infile.output().open('r') as inputs:
                #Each pdb should be a single line
                logger.debug("Calculating dependencies from %s"%self.input_list)
                deps =  [ self.makeTask(pdb.strip())
                        for pdb in inputs
                        if pdb.strip() and pdb[0]!='#' ]
                for dep in deps:
                    logger.debug("Requiring %s"%dep)#(dep.__class__.__name__,dep.pdb if dep is not None else None))
                    yield dep

    def makeTask(self,pdb):
        logger.info("Creating EppicCli task for %s"%pdb)
        outputdir = os.path.join(self.wui_files, "data", "divided", pdb[1:3], pdb)
        logfile = os.path.join(outputdir,pdb+".out")
        return EppicCli(pdb=pdb,
                    out=outputdir,
                    log=logfile)

@inherits(EppicList)
class SGEEppicList(EppicList):
    def makeTask(self,pdb):
        outputdir = os.path.join(self.wui_files, "data", "divided", pdb[1:3], pdb)
        logfile = os.path.join(outputdir,pdb+".out")
        return SGEEppicCli(pdb=pdb,
                    out=outputdir,
                    log=logfile)


@requires(SGEEppicList)
class Main(luigi.WrapperTask):
    pass
