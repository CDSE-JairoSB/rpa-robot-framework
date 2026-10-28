*** Settings ***
Documentation       Orquestador RPA para actualizar precios de una wishlist Amazon.
...                 Flujo: Tasks -> Business Keywords -> System Keywords -> bibliotecas Python.

Resource            ../resources/common/settings.resource
Resource            ../keywords/amazon/auth_flow.resource
Resource            ../keywords/amazon/wishlist_price_processing.resource
Resource            ../keywords/common/system/browser_keywords.resource
Resource            ../keywords/amazon/wishlist_notification.resource

Suite Setup         Inicializar Proceso RPA
Suite Teardown      Finalizar Proceso RPA


*** Tasks ***
Actualizar Precios De Wishlist Amazon
    [Documentation]    Consulta la wishlist autorizada y registra precios en el histórico CSV.
    Verificar Acceso A Wishlist Amazon
    ...    ${LOCATORS}[authentication][login_form]
    ...    ${LOCATORS}[authentication][captcha]
    ...    ${LOCATORS}[errors][robot_check]
    ...    ${LOCATORS}[errors][page_error]
    Actualizar Wishlist Amazon


*** Keywords ***
Inicializar Proceso RPA
    [Documentation]    Carga configuración, localizadores e inicia Chrome con el perfil autorizado.
    Cargar Configuracion Y Parametros
    Iniciar Sesion En Portal
    Log    Actualizador de wishlist inicializado en ambiente: ${ENV}    level=INFO

Finalizar Proceso RPA
    [Documentation]    Genera métricas y cierra el navegador aunque el flujo falle.
    Registrar Resumen De Ejecucion
    Run Keyword And Ignore Error    Cerrar Sesion Del Navegador
    Log    Ciclo de actualización de wishlist finalizado.    level=INFO
