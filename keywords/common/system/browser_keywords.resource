*** Settings ***
Documentation       Low-level browser keywords for safe Amazon wishlist extraction.

Resource            ../../../resources/common/settings.resource


*** Keywords ***
Inicializar Navegador
    [Documentation]    Opens a standard browser without reusing a user profile.
    [Arguments]    ${url}    ${headless}=${False}    ${timeout}=15
    Set Selenium Timeout    ${timeout} seconds
    ${env_headless}=    Get Environment Variable    CHROME_HEADLESS    default=${EMPTY}
    ${global_headless}=    Get Variable Value    ${HEADLESS}    ${False}
    ${headless_str}=    Convert To String    ${headless}
    ${global_headless_str}=    Convert To String    ${global_headless}
    ${effective_headless}=    Evaluate
    ...    '${headless_str}'.lower() in ['true', '1', 'yes'] or '${global_headless_str}'.lower() in ['true', '1', 'yes'] or '${env_headless}'.lower() in ['true', '1', 'yes']
    Open Available Browser
    ...    ${url}
    ...    browser_selection=chrome
    ...    headless=${effective_headless}
    ...    maximized=${True}
    Log    Browser started at URL: ${url} (Headless: ${effective_headless})    level=INFO

Inicializar Navegador Con Copia Temporal De Perfil
    [Documentation]    Copies a closed Chrome profile to a temporary user-data directory and starts Chrome from that copy.
    [Arguments]    ${url}    ${profile_path}    ${profile_name}=Default    ${timeout}=20
    Should Not Be Empty    ${profile_path}    msg=Provide the Chrome profile directory to copy.
    Directory Should Exist    ${profile_path}
    ${timestamp}=    Get Current Date    result_format=%Y%m%d_%H%M%S
    ${temporary_root}=    Set Variable    ${TEMP_DIR}${/}chrome_profile_${profile_name}_${timestamp}
    Copy Chrome User Data    ${profile_path}    ${profile_name}    ${temporary_root}
    Set Suite Variable    ${TEMPORARY_CHROME_PROFILE_ROOT}    ${temporary_root}
    ${debug_port}=    Set Variable    9223
    ${binary_override}=    Get Variable Value    ${AMAZON_CHROME_BINARY_PATH}    ${EMPTY}
    ${chrome_binary}=    Resolve Chrome Binary Path    ${binary_override}
    ${env_headless}=    Get Environment Variable    CHROME_HEADLESS    default=${EMPTY}
    ${is_headless}=    Get Variable Value    ${HEADLESS}    ${False}
    ${is_headless_str}=    Convert To String    ${is_headless}
    @{chrome_args}=    Create List
    ...    --remote-debugging-port\=${debug_port}
    ...    --user-data-dir\=${temporary_root}
    ...    --profile-directory\=${profile_name}
    ...    --no-first-run
    ...    --no-default-browser-check
    IF    '${is_headless_str}'.lower() in ['true', '1', 'yes'] or '${env_headless}'.lower() in ['true', '1', 'yes']
        Append To List    ${chrome_args}    --headless=new
        Append To List    ${chrome_args}    --disable-gpu
        Append To List    ${chrome_args}    --no-sandbox
        Append To List    ${chrome_args}    --disable-dev-shm-usage
    ELSE
        Append To List    ${chrome_args}    --start-maximized
    END
    ${chrome_process}=    Start Process
    ...    ${chrome_binary}
    ...    @{chrome_args}
    Set Suite Variable    ${CHROME_PROFILE_PROCESS}    ${chrome_process}
    Process Should Be Running    ${chrome_process}
    Set Selenium Timeout    ${timeout} seconds
    Wait Until Keyword Succeeds
    ...    ${timeout} seconds
    ...    1 second
    ...    Attach Chrome Browser
    ...    port=${debug_port}
    Go To    ${url}
    Log    Chrome started from the temporary copy of profile '${profile_name}'.    level=INFO

Cerrar Sesion Del Navegador
    [Documentation]    Closes browser sessions, stops a native Chrome process if any, and removes a temporary profile copy.
    Close All Browsers
    ${chrome_process}=    Get Variable Value    ${CHROME_PROFILE_PROCESS}    ${None}
    IF    $chrome_process is not None    Terminate Process    ${chrome_process}
    ${temporary_root}=    Get Variable Value    ${TEMPORARY_CHROME_PROFILE_ROOT}    ${None}
    IF    $temporary_root is not None
        OperatingSystem.Remove Directory    ${temporary_root}    recursive=${True}
    END
    Log    Browsers closed successfully.    level=INFO

Verificar Acceso A Wishlist Amazon
    [Documentation]    Fails safely on login, CAPTCHA, robot check, or an error page; never attempts to solve them.
    [Arguments]    ${login_locator}    ${captcha_locator}    ${robot_check_locator}    ${error_locator}
    ${requires_login}=    Run Keyword And Return Status    Page Should Contain Element    ${login_locator}
    IF    ${requires_login}
        Fail    [BUSINESS_EXCEPTION] Amazon requires sign-in. Verify the authorized Chrome profile.
    END
    ${has_captcha}=    Run Keyword And Return Status    Page Should Contain Element    ${captcha_locator}
    IF    ${has_captcha}
        Fail    [BUSINESS_EXCEPTION] Amazon presented a CAPTCHA; this robot does not attempt to solve it.
    END
    ${has_robot_check}=    Run Keyword And Return Status    Page Should Contain Element    ${robot_check_locator}
    IF    ${has_robot_check}
        Fail    [BUSINESS_EXCEPTION] Amazon blocked automation and requires human intervention.
    END
    ${has_page_error}=    Run Keyword And Return Status    Page Should Contain Element    ${error_locator}
    IF    ${has_page_error}
        Fail    [SYSTEM_EXCEPTION] Amazon displayed an error page for the wishlist.
    END

Extraer Articulos Visibles De Wishlist
    [Documentation]    Extracts name, URL, price, and availability from visible cards through the DOM.
    [Arguments]    ${item_cards}    ${item_title}    ${item_link}    ${item_price}    ${item_availability}
    ${items}=    Execute JavaScript
    ...    const cards = Array.from(document.querySelectorAll(arguments[0])); return cards.map((card) => { const title = card.querySelector(arguments[1]); const link = card.querySelector(arguments[2]); const price = card.querySelector(arguments[3]); const availability = card.querySelector(arguments[4]); return { product_name: (title?.innerText || '').trim(), product_url: link?.href || '', raw_price: (price?.innerText || '').trim(), availability: (availability?.innerText || '').trim() }; }).filter((item) => item.product_name || item.product_url);
    ...    ${item_cards}
    ...    ${item_title}
    ...    ${item_link}
    ...    ${item_price}
    ...    ${item_availability}
    RETURN    ${items}
