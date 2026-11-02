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
    IF    $profile_path != ''
        Log    Parámetros locales resueltos. Perfil Chrome: ${profile_path}    level=INFO
    ELSE
        Log
        ...    Parámetros locales resueltos. Sin perfil Chrome especificado; se usará sesión limpia aislada.
        ...    level=INFO
    END

Solicitar Dato Local
    [Documentation]    Pide un valor al operador cuando no hay CLI, env ni config/local.yaml (solo en sesiones interactivas).
    [Arguments]    ${mensaje}
    ${is_headless}=    Get Variable Value    ${HEADLESS}    ${False}
    ${env_headless}=    Get Environment Variable    CHROME_HEADLESS    default=${EMPTY}
    ${is_ci}=    Get Environment Variable    CI    default=${EMPTY}
    ${is_non_interactive}=    Evaluate
    ...    str($is_headless).lower() in ['true', '1', 'yes'] or str($env_headless).lower() in ['true', '1', 'yes'] or str($is_ci).lower() in ['true', '1', 'yes']
    IF    ${is_non_interactive}
        Fail
        ...    Entorno desatendido (CI/Headless): Falta configurar '${mensaje}'. Defínalo en variables de entorno, secretos o config/local.yaml.
    END
    TRY
        ${valor}=    Get Value From User    ${mensaje}
    EXCEPT    AS    ${error}
        Fail    No se pudo solicitar '${mensaje}' de forma interactiva: ${error}. Defina el valor en config/local.yaml.
    END
    RETURN    ${valor}
