*** Settings ***
Documentation       Archivo central de orquestación de librerías, recursos y configuración común.

# Librerías Estándar de Robot Framework
Library             Collections
Library             OperatingSystem
Library             String
Library             DateTime
Library             Process

# Librerías Especializadas RPA (rpaframework)
Library             RPA.Browser.Selenium
Library             RPA.FileSystem
Library             RPA.Tables
Library             RPA.Excel.Files
Library             RPA.PDF

# Librerías Personalizadas Python
Library             ../../libraries/DataProcessor.py
Library             ../../libraries/PriceTracker.py

# Variables Globales
Resource            variables/global_variables.resource
