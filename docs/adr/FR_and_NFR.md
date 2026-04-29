# Functional Requirements (FRs)
- FR-01 (Data Ingestion): Securely fetch patient data via FHIR API.
- FR-02 (PII Masking): Anonymize PII using a localized Edge LLM.
- FR-03 (HITL Verification): Provide a UI for manual verification and approval.
- FR-04 (Session Persistence): Allow session recovery without persisting raw PII to disk.

# Non-Functional Requirements (NFRs) and Design Influence:
- NFR-01 Security & Confidentiality: MediMask utilizes an Edge Computing pattern.
  - This ensures that the Local LLM Engine remains within the hospital's air-gapped environment, complying with Japan's 2G3M guidelines and mitigating the confidentiality risks of cloud-based LLMs.
- NFR-02 Ethical Integrity and Consent: This requirement led to the implementation of the "Deny by Default" methodology within the Input Validation module,
  - ensuring that no data is fetched or processed without an explicit patient "opt-in," thereby upholding ethical data autonomy.
- NFR-03 Accountability & Reliability: The HITL UI forces a human-in-the-loop verification step.
  - This ensures algorithmic fairness and provides a clear audit point for every anonymization decision.
- NFR-04 Privacy-Preserving Persistence: The design adopts a "Zero-Disk-Write" policy for PII.
  - This requirement influenced the decision to use the Database Access Manager to store only record hashes and character offsets in the Database (SQLite), ensuring that even a physical breach of the local storage would yield no readable patient information.
- NFR-05 Performance & Efficiency: The constraint of running high-performance LLMs on limited edge hardware influenced the creation of the Task Queue Manager.
  - By applying architectural patterns suited for scalability and performance (Walker, 2022), MediMask achieves optimal GPU utilization through the pipelining of inference jobs.
