*** Settings ***
Documentation       Resolución de parámetros locales sin versionar secretos ni paths personales.

Resource            ../../../resources/common/settings.resource


*** Keywords ***
Resolver Parametros Locales Amazon
    [Documentation]    CLI > env > config/local.yaml > perfil Chrome por defecto > diálogo.
    ${local}=    Load Local Config    config/local.yaml
    ${url}=    Resolve Runtime Value
    ...    ${AMAZON_WISHLIST_URL}
    ...    AMAZON_WISHLIST_URL
    ...    ${local}
    ...    amazon.wishlist_url
    IF    $url == ''
        ${url}=    Solicitar Dato Local    URL de la wishlist Amazon (no se guarda en git)
    END
    Should Not Be Empty
    ...    ${url}
    ...    msg=Falta la URL de wishlist. Use el diálogo, config/local.yaml (copie local.yaml.example) o --variable AMAZON_WISHLIST_URL.

    ${profile_name}=    Resolve Runtime Value
    ...    ${EMPTY}
    ...    AMAZON_CHROME_PROFILE_NAME
    ...    ${local}
    ...    amazon.chrome_profile_name
    ...    Default
    ${default_profile}=    Default Chrome Profile Path    ${profile_name}
    ${profile_path}=    Resolve Runtime Value
    ...    ${AMAZON_CHROME_USER_DATA_DIR}
    ...    AMAZON_CHROME_USER_DATA_DIR
    ...    ${local}
    ...    amazon.chrome_profile_path
    ...    ${default_profile}
    IF    $profile_path == ''
        ${profile_path}=    Solicitar Dato Local    Ruta del perfil Chrome (debe terminar en ${profile_name})
    END
    Should Not Be Empty
    ...    ${profile_path}
    ...    msg=Falta la ruta del perfil Chrome. Use config/local.yaml o --variable AMAZON_CHROME_USER_DATA_DIR.

    ${binary_path}=    Resolve Runtime Value
    ...    ${AMAZON_CHROME_BINARY_PATH}
    ...    AMAZON_CHROME_BINARY_PATH
    ...    ${local}
    ...    amazon.chrome_binary_path
    ...    ${EMPTY}

    Set Global Variable    ${AMAZON_WISHLIST_URL}    ${url}
    Set Global Variable    ${AMAZON_CHROME_USER_DATA_DIR}    ${profile_path}
    Set Global Variable    ${AMAZON_CHROME_PROFILE_NAME}    ${profile_name}
    Set Global Variable    ${AMAZON_CHROME_BINARY_PATH}    ${binary_path}
    Log    Parámetros locales resueltos. Perfil Chrome: ${profile_name}    level=INFO

Solicitar Dato Local
    [Documentation]    Pide un valor al operador cuando no hay CLI, env ni config/local.yaml.
    [Arguments]    ${mensaje}
    TRY
        ${valor}=    Get Value From User    ${mensaje}
    EXCEPT    AS    ${error}
        Fail    No se pudo solicitar '${mensaje}' de forma interactiva: ${error}. Defina el valor en config/local.yaml.
    END
    RETURN    ${valor}
