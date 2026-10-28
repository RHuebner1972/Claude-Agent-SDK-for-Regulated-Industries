# ENG-SOP-021: Engineering Change Board with AI assistance (synthetic, for course use)

Northgate Precision Components, Inc. (fictional). Programs: FALCON (defense, CUI and ITAR) and HARBORLIGHT (commercial).

1. The Change Control Board (CCB) assistant runs on the company's general AI platform, used by staff who are not all cleared for CUI or authorized for ITAR technical data. It may see ECR metadata only: ID, program, part number, title, class, requester, status.
2. Technical details of FALCON ECRs (drawings, dimensions, tolerances, materials, test notes) are CUI and ITAR technical data. Only the **cleared engineering assistant**, running inside the CUI enclave, may read them.
3. The cleared assistant returns a **change impact summary** in a fixed format (ENG-FORM-7): no dimensions, tolerances, materials, drawing numbers or test data. Anything else is stripped; a summary that contains controlled content is rejected.
4. Each program's cleared assistant may read only its own program's ECRs.
5. The enclave keeps its own audit log. CUI never goes into the general platform's logs.
6. Model inference and storage for the enclave stay in a U.S. region of a provider offering FedRAMP Moderate-equivalent controls (DFARS 252.204-7012(b)(2)(ii)(D)); access is limited to U.S. persons.
