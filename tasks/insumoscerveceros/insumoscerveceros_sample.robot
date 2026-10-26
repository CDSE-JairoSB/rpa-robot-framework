*** Settings ***
Documentation       Sample base: Chrome, navegación, lectura de etiqueta y cierre seguro.
Resource            ../../resources/common/settings.resource
Resource            ../../keywords/common/system/browser_keywords.resource

Suite Setup         Abrir Sitio De Prueba En Chrome
Suite Teardown      Cerrar Sesion Del Navegador

*** Variables ***
${SAMPLE_URL}      https://insumoscerveceros.mx/collections/fermentacion
${PAGE_HEADING}    xpath=(//h1[normalize-space()='Fermentación'])[1]

*** Tasks ***
Validar Navegacion Y Lectura De Encabezado
    [Documentation]    Comprueba que Chrome abre el sitio y que el encabezado Fermentación está disponible.
    Wait Until Element Is Visible    ${PAGE_HEADING}    timeout=20 seconds
    ${heading}=    Get Text    ${PAGE_HEADING}
    Should Be Equal    ${heading}    Fermentación
    Log To Console    Encabezado leído correctamente: ${heading}
    Log    Validación de navegación completada. Encabezado: ${heading}    level=INFO

*** Keywords ***
Abrir Sitio De Prueba En Chrome
    [Documentation]    Inicia una instancia limpia de Chrome y abre el sitio asignado.
    Inicializar Navegador    ${SAMPLE_URL}    headless=${False}    timeout=20
