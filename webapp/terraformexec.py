
import os
import argparse
import json
import sys
import logging
import subprocess
import shutil


class Terraform(object):
    def __init__(self, az_subscription_id, az_client_id, az_client_secret, az_tenant_id, az_access_key,
                 backendFile, varFiles,logger,  use_apply=True, run_output=True, applyAutoApprove=True,  variables=None,
                 planout="out.tfplan", outputazdo=None, terraformversion="0.12.8", verbose=False, useazcli = False):
        self.backendFile = backendFile
        self.varFiles = varFiles
        self.variables = dict() if variables is None else variables
        self.use_apply = use_apply
        self.applyAutoApprove = applyAutoApprove
        self.planout = planout
        self.outputazdo = outputazdo
        self.run_output = run_output
        self.terraform_version = terraformversion
        self.verbose = verbose
        self.logger = logger
        self.useazcli = useazcli

        if self.useazcli == True:
            os.system("az login --service-principal -u "+az_client_id+" -p " + az_client_secret+" --tenant "+az_tenant_id+"")
            os.system("az account set --subscription "+az_subscription_id+"")

        os.environ["ARM_SUBSCRIPTION_ID"] = az_subscription_id
        os.environ["ARM_CLIENT_ID"] = az_client_id
        os.environ["ARM_CLIENT_SECRET"] = az_client_secret
        os.environ["ARM_TENANT_ID"] = az_tenant_id
        os.environ["ARM_ACCESS_KEY"] = az_access_key



    def Init(self):
        self.logger.info("=> Run Terrform init")
        self.logger.info("[terraform init -no-color -backend-config=" +self.backendFile+" -reconfigure]")
        os.system("terraform init -no-color -backend-config=" +self.backendFile+" -reconfigure")


    def Plan(self):
        print("=> Run Terrform plan")
        cmd = ""

        for file in self.varFiles:
            cmd += " -var-file="+file
        for var in self.variables:
            cmd += """ -var "{}={}" """.format(var["name"], var["value"])

        cmd += " -out "+self.planout

        self.logger.info("[terraform plan -no-color -detailed-exitcode "+cmd+"]")
        commandplan = os.system("terraform plan -no-color -detailed-exitcode "+cmd)

        '''working_folder = self.working_dir
        stderr = subprocess.PIPE
        stdout = subprocess.PIPE
        p = subprocess.Popen("terraform plan -no-color -detailed-exitcode {}".format(cmd), stdout=stdout, stderr=stderr, cwd=working_folder)
        out, err = p.communicate()
        ret_code = p.returncode
        print (out)
        print(ret_code)
        '''

        return commandplan

    def Apply(self):
        self.logger.info("=> Run Terraform Apply")
        cmd = ""

        if self.applyAutoApprove:
            cmd += "-auto-approve"
            cmd += " "+self.planout
        else:
            for file in self.varFiles:
                cmd += " -var-file="+file
            for var in self.variables:
                cmd += """ -var "{}={}" """.format(var["name"], var["value"])

        self.logger.info("[terraform apply -no-color "+cmd+"]")
        ret = os.system("terraform apply "+cmd)

        return ret

    def Destroy(self):
        print("=> Run Terrform destroy")
        cmd = ""

        for file in self.varFiles:
            cmd += " -var-file="+file
        for var in self.variables:
            cmd += """ -var "{}={}" """.format(var["name"], var["value"])

        cmd += " -auto-approve"

        self.logger.info("[terraform destroy -no-color "+cmd+"]")
        return os.system("terraform destroy -no-color "+cmd)

    def Output(self):
        self.logger.info("=> Run terraform output")
        self.logger.info("[terraform output -json]")
        outputjson = os.popen("terraform output -json").read()
        self.logger.info(outputjson)

        # change the JSON string into a JSON object
        jsonObject = json.loads(outputjson)

        with open('outputtf.json', 'w', encoding='utf-8') as outfile:
            json.dump(jsonObject, outfile, indent = 4)
            self.logger.info("[INFO : Write outputtf.json]")

        for output in self.outputazdo:
            tfoutput_name = output["tfoutput"]
            azdovar = output["azdovar"]
            if tfoutput_name in jsonObject.keys():
                var_value = jsonObject[tfoutput_name]["value"]
                print(var_value)
                os.system(
                    "echo ##vso[task.setvariable variable="+azdovar+";]"+var_value+"")
            else:
                print("key {} is not present in terraform output".format(
                    tfoutput_name))
        return outputjson

    def CheckIfDestroy(self):
        self.logger.info("=> Check if Terraform Destroy")
        plan = os.popen("terraform show -json "+self.planout +
                        " | jq .resource_changes[].change.actions[]").read()


        finddelete = plan.find("delete")
        if finddelete > 0:
            self.logger.info("DESTROY : Terraform can't be done")
            return True
        else:
            self.logger.info("Great there is no destroy")
            return False

    def Clean(self):
        if os.path.exists(self.planout):
            self.logger.info("Delete the "+self.planout+" file")
            os.remove(self.planout)
        if os.path.exists(".terraform"):
            self.logger.info("Delete the .terraform folder")
            shutil.rmtree(".terraform")


if __name__ == "__main__":

    logger = logging.getLogger()
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.info("====> Start Terraform execution")

    parser = argparse.ArgumentParser()

    # authentification Azure pour Terraform avec Service Principal, pour overrider le fichier json de config
    parser.add_argument("--subscriptionId", required=False,
                        help="Azure SubscriptionId Id")
    parser.add_argument("--clientId", required=False, help="Azure Client Id")
    parser.add_argument("--clientSecret", required=True,
                        help="Azure Client Secret")
    parser.add_argument("--tenantId", required=False, help="Azure Tenant Id")
    parser.add_argument("--accessKey", required=False, help="Azure Access Key for storage backend")

    # fichier json de config
    parser.add_argument("--configfile", required=True,
                        help="Configuration file json")

    # permet a Terraform d'appliquer les changements
    parser.add_argument("--apply", help="Run Terraform apply",
                        action="store_true")

    # permet a Terraform de detruire les resources
    parser.add_argument("--acceptdestroy", help="Accept Terraform Destroy operation",
                        action="store_true")

    # Terraform execute destroy au lieu de apply
    parser.add_argument("--destroy", help="Execute Terraform Destroy",
                        action="store_true")

    # verbose mode
    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                        action="store_true")

    args = parser.parse_args()

    with open(args.configfile) as config:
        data = json.load(config)

    useazcli = data["use_azcli"]
    backendfile = data["backendfile"]
    autoapprove = data["auto-approve"]
    varfiles = data["varfiles"]  # array of files
    variables = data["vars"]  # dict of variable name : value
    outplan = data["planout"]
    outputAzdo = data["OutputToAzDo"]
    terraformoutput = data["run_output"]
    downloadterraform = data["download_terraform"]
    terraformversion = data["terraform_version"]

    applyterraform = data["run_apply"]
    if(args.apply == False): applyterraform = "false"

    if "subscriptionId" in data["azure_credentials"]:
        azSubscriptionId = data["azure_credentials"]["subscriptionId"]
    if(args.subscriptionId != None): azSubscriptionId = args.subscriptionId

    if "clientId" in data["azure_credentials"]:
        azClientId = data["azure_credentials"]["clientId"]
    if(args.clientId != None): azClientId = args.clientId

    if "tenantId" in data["azure_credentials"]:
        azTenantId = data["azure_credentials"]["tenantId"]
    if(args.tenantId != None): azTenantId = args.tenantId

    if "accessKey" in data["azure_credentials"]:
        azAccessKey = data["azure_credentials"]["accessKey"]
    if(args.accessKey != None): azAccessKey = args.accessKey

    acceptDestroy = args.acceptdestroy

    # Affichage des arguments et de la config si -v
    if args.verbose:
        logger.info("========== DEBUG MODE =========================")
        logger.info("useazcli: "+str(useazcli))
        logger.info("backendfile: "+str(backendfile))
        logger.info("autoapprove: "+str(autoapprove))
        logger.info("varfiles: "+str(varfiles))
        logger.info("variables: "+str(variables))
        logger.info("outplan: "+str(outplan))
        logger.info("outputAzdo: "+str(outputAzdo))
        logger.info("terraformoutput: "+str(terraformoutput))
        logger.info("downloadterraform: "+str(downloadterraform))
        logger.info("terraformversion: "+str(terraformversion))
        logger.info("applyterraform: "+str(applyterraform))
        logger.info("acceptDestroy: "+str(acceptDestroy))
        logger.info("verbose: "+str(args.verbose))
        logger.info("azSubscriptionId: "+str(azSubscriptionId))
        logger.info("azClientId: "+str(azClientId))
        logger.info("azTenantId: "+str(azTenantId))
        logger.info("================================================")

    # Appel du constructeur
    t = Terraform(azSubscriptionId, azClientId, args.clientSecret, azTenantId, azAccessKey,
                  backendfile, varfiles,logger, applyAutoApprove=autoapprove, variables=variables, planout=outplan,
                  outputazdo=outputAzdo, use_apply=applyterraform, run_output=terraformoutput, terraformversion=terraformversion, useazcli=useazcli)

    # Terraform Init
    t.Init()

    if(args.destroy == True):
        # Terraform Destroy
        t.Destroy()
    else:

        # Terraform Plan
        plan_ret_code = t.Plan()
        logger.info("Plan return code: {}".format(plan_ret_code))

        # Si erreur dans le plan de Terraform
        if(plan_ret_code in [1,256]):
            sys.exit("Error in Terraform plan")
        else:
            if(plan_ret_code in [2,512]): # plan need changes
                if (t.use_apply == True):
                    terraformdestroy = False # Est ce qu'il va avoir des delete , default false
                    if(acceptDestroy == False):
                        terraformdestroy = t.CheckIfDestroy() # check dans le plan

                        if(terraformdestroy == False):
                            # Terraform Apply

                            apply_ret_code = t.Apply()
                            logger.info("Apply return code: {}".format(apply_ret_code))
                            if(apply_ret_code in [1,256]):
                                sys.exit("Error in Terraform apply")

                        else:
                            sys.exit("Error Terraform will be destroy resources")

                    if(acceptDestroy == True):
                        # Terraform Apply with acceptDestroy
                        apply_ret_code = t.Apply()
                        logger.info("Apply return code: {}".format(apply_ret_code))
                        if(apply_ret_code in [1,256]):
                            sys.exit("Error in Terraform apply")
                else:
                    logger.info("=> Terraform apply is skipped")

        ret =""
        if(plan_ret_code in [0,2,512]): ## no changes or changes
            # Terraform Output tf => Azure DevOps variables
            if(t.run_output == True):
                ret = t.Output()
            else:
                logger.info("==> Terraform output is skipped")

        #clean folder
        t.Clean()

    logger.info("====> End Terraform execution")