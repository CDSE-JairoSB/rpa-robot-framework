*** Settings ***
Documentation       Metrics and operational traceability for the Amazon wishlist updater.
Resource            ../../resources/common/settings.resource

*** Keywords ***
Registrar Resumen De Ejecucion
    [Documentation]    Prints the final Amazon price-update summary.
    ${total}=          Get Variable Value    ${TOTAL_ITEMS}    0
    ${success}=        Get Variable Value    ${SUCCESSFUL_ITEMS}    0
    ${decreases}=      Get Variable Value    ${PRICE_DECREASES}    0
    ${increases}=      Get Variable Value    ${PRICE_INCREASES}    0
    ${unavailable}=    Get Variable Value    ${UNAVAILABLE_ITEMS}    0
    ${business}=       Get Variable Value    ${BUSINESS_EXCEPTIONS}    0
    ${system}=         Get Variable Value    ${SYSTEM_EXCEPTIONS}    0

    Log To Console    \n======================================================
    Log To Console    AMAZON WISHLIST UPDATE SUMMARY
    Log To Console    ======================================================
    Log To Console    Items processed: ${total}
    Log To Console    Available prices: ${success}
    Log To Console    Price decreases: ${decreases}
    Log To Console    Price increases: ${increases}
    Log To Console    No price or unavailable: ${unavailable}
    Log To Console    Business exceptions: ${business}
    Log To Console    System exceptions: ${system}
    Log To Console    ======================================================

    Log
    ...    Total=${total}; priced=${success}; decreases=${decreases}; increases=${increases}; unavailable=${unavailable}; business=${business}; system=${system}
    ...    level=INFO
