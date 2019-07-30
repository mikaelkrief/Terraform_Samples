
provider "azurerm" {}

##### RG
resource "azurerm_resource_group" "test" {
  name     = "rg_test"
  location = "West Europe"
}


### NETWORK
resource "azurerm_virtual_network" "test" {
  name                = "vnet_test"
  address_space       = ["10.0.0.0/16"]
  location            = "${azurerm_resource_group.test.location}"
  resource_group_name = "${azurerm_resource_group.test.name}"
}

resource "azurerm_subnet" "test" {
  name                 = "subnet1"
  resource_group_name  = "${azurerm_resource_group.test.name}"
  virtual_network_name = "${azurerm_virtual_network.test.name}"
  address_prefix       = "10.0.1.0/24"

  delegation {
    name = "delegation"

    service_delegation {
      name    = "Microsoft.Web/serverFarms"
      actions = ["Microsoft.Network/virtualNetworks/subnets/action"]
    }
  }
}

##### APP SERVICE
resource "azurerm_app_service_plan" "test" {
  name                = "example-appserviceplan"
  location            = "${azurerm_resource_group.test.location}"
  resource_group_name = "${azurerm_resource_group.test.name}"

  sku {
    tier = "Standard"
    size = "S1"
  }
}

resource "azurerm_app_service" "test" {
  name                = "example-app-service-demovnet"
  location            = "${azurerm_resource_group.test.location}"
  resource_group_name = "${azurerm_resource_group.test.name}"
  app_service_plan_id = "${azurerm_app_service_plan.test.id}"

  site_config {
    dotnet_framework_version = "v4.0"
    scm_type                 = "LocalGit"
  }
  depends_on = ["azurerm_subnet.test"]
}

### ARM resource for ADD the VNET integration
resource "azurerm_template_deployment" "appservicevnetarm" {
  name                = "appservicevnetarmARM"
  resource_group_name = "${azurerm_resource_group.test.name}"
  template_body       = "${file("ARM_appserviceVnet.json")}"

  parameters = {
    siteName          = "${azurerm_app_service.test.name}"
    subnetId          = "${azurerm_subnet.test.id}"
  }

  deployment_mode     = "Incremental"
  depends_on = ["azurerm_app_service.test","azurerm_subnet.test"]
}