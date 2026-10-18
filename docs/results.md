# Test Results

Eight questions run with `python retrieval_debugger.py -q "..."` on the current code. For each one: the answer as returned, and the five chunks the Cross-Encoder passed to the model.

PDPL = Personal Data Protection Law, PDBIG = Personal Data Breach Incidents Procedural Guide. *Found by* is the retriever that proposed the chunk (semantic search, BM25, or both).

## 1. Personal data (Art. 1)

**Q:** What is personal data according to Article 1?

>According to Article 1, personal data is defined as any data, regardless of its source or form, that may lead to identifying an individual specifically or that may directly or indirectly make it possible to identify an individual, including name, personal identification number, addresses, contact numbers, license numbers, records, personal assets, bank and credit card numbers, photos and videos of an individual, and any other data of personal nature [PDPL · Article 1 · p. 2].

| # | Chunk | Citation | Rerank score | Found by |
|---|---|---|---|---|
| 1 | 1 | PDPL · Article 1 · p. 2 | 6.9894 | Semantic |
| 2 | 21 | PDPL · Articles 19, 20, 21 · p. 9 | 4.4980 | Semantic + BM25 |
| 3 | 12 | PDPL · Article 11 · p. 6 | 3.9614 | BM25 |
| 4 | 16 | PDPL · Articles 14, 15 · p. 7 | 3.3750 | Semantic + BM25 |
| 5 | 19 | PDPL · Article 18 · p. 8 | 3.1486 | BM25 |

## 2. Processing without consent (Art. 6)

**Q:** In which cases may Personal Data be processed without the consent of the Data Subject under Article 6?

>Under Article 6 of the PDPL, Personal Data may be processed without the Data Subject’s consent in the following cases:
> 
> 1. When the processing serves the actual interests of the Data Subject but communicating with them is impossible or difficult.  
> 2. When the processing is pursuant to another law or in implementation of a previous agreement to which the Data Subject is a party.  
> 3. When the Controller is a Public Entity and the processing is required for security purposes or to satisfy judicial requirements.  
> 4. When the processing is necessary for the legitimate interests of the Controller, without prejudice to the rights and interests of the Data Subject, and provided no Sensitive Data is processed.  
> 
> [PDPL · Article 6 · p. 4] (cases 1‑3)  
> [PDPL · Articles 7, 8 · p. 5] (case 4)

| # | Chunk | Citation | Rerank score | Found by |
|---|---|---|---|---|
| 1 | 8 | PDPL · Article 6 · p. 4 | 9.3053 | Semantic + BM25 |
| 2 | 16 | PDPL · Articles 14, 15 · p. 7 | 6.3728 | Semantic |
| 3 | 15 | PDPL · Article 14 · p. 7 | 6.1652 | Semantic + BM25 |
| 4 | 9 | PDPL · Articles 7, 8 · p. 5 | 5.5896 | Semantic + BM25 |
| 5 | 24 | PDPL · Articles 26, 27 · p. 10 | 4.9835 | Semantic + BM25 |

## 3. Sensitive data

**Q:** What is Sensitive Data?

>Sensitive Data is defined as Personal Data revealing racial or ethnic origin, religious, intellectual or political belief, data relating to security criminal convictions and offenses, biometric or Genetic Data for the purpose of identifying the person, Health Data, and data that indicate… [PDPL · p. 2]

| # | Chunk | Citation | Rerank score | Found by |
|---|---|---|---|---|
| 1 | 25 | PDPL · p. 10 | 1.4695 | Semantic + BM25 |
| 2 | 17 | PDPL · p. 7 | 0.6699 | Semantic + BM25 |
| 3 | 2 | PDPL · p. 2 | 0.5354 | Semantic + BM25 |
| 4 | 12 | PDPL · Article 11 · p. 6 | -0.5482 | BM25 |
| 5 | 24 | PDPL · Articles 26, 27 · p. 10 | -1.4603 | Semantic + BM25 |

## 4. Notifying SDAIA

**Q:** When must a Controller notify SDAIA about a personal data breach?

>A Controller must notify SDAIA within **72 hours** of becoming aware of a personal data breach, **if the breach is expected to harm personal data or data subjects, or conflict with their rights or interests** [PDBIG · p. 5]. The Personal Data Protection Law also requires the Controller to notify the Competent Authority (SDAIA) upon knowing of any breach, damage, or illegal access to personal data, in accordance with the Regulations [PDPL · Articles 19, 20, 21 · p. 9].

| # | Chunk | Citation | Rerank score | Found by |
|---|---|---|---|---|
| 1 | 45 | PDBIG · p. 5 | 8.4638 | Semantic + BM25 |
| 2 | 43 | PDBIG · p. 4 | 7.0807 | Semantic + BM25 |
| 3 | 50 | PDBIG · p. 7 | 6.2694 | Semantic + BM25 |
| 4 | 47 | PDBIG · p. 6 | 4.7274 | Semantic + BM25 |
| 5 | 21 | PDPL · Articles 19, 20, 21 · p. 9 | 4.6904 | Semantic + BM25 |

## 5. Breach handling stages

**Q:** What are the three stages for handling a personal data breach incident?

>The three stages for handling a personal data breach incident are:
> 
> 1. **STAGE ONE: SDAIA Notice** – The Controller must notify SDAIA within 72 hours of becoming aware of the incident.  
> 2. **STAGE TWO: Breach Incident Containment** – The Controller implements response and containment measures.  
> 3. **STAGE THREE: Documentation** – The Controller retains records of the incident, corrective actions, and relevant documents.  
> 
> [PDBIG · p. 3] [PDBIG · p. 5] [PDBIG · p. 6] [PDBIG · p. 7]

| # | Chunk | Citation | Rerank score | Found by |
|---|---|---|---|---|
| 1 | 47 | PDBIG · p. 6 | 7.5693 | Semantic + BM25 |
| 2 | 50 | PDBIG · p. 7 | 7.0508 | Semantic + BM25 |
| 3 | 45 | PDBIG · p. 5 | 6.6094 | Semantic + BM25 |
| 4 | 42 | PDBIG · p. 3 | 3.1757 | Semantic + BM25 |
| 5 | 46 | PDBIG · p. 5 | 1.8945 | Semantic + BM25 |

## 6. Breach risks

**Q:** What are the possible risks or consequences of a personal data breach mentioned in the procedural guide?

>The procedural guide identifies several possible risks or consequences of a personal data breach:
> 
> - Economic damages, such as fraud or identity theft [PDBIG · p. 7].
> - Physical harm, such as stalking and assault [PDBIG · p. 6].
> - Economic damage, such as fraud [PDBIG · p. 6].
> - Damages related to exercising the data subject’s rights [PDBIG · p. 6].
> - More generally, actual or potential consequences and risks to personal data or the data subject [PDBIG · p. 5].

| # | Chunk | Citation | Rerank score | Found by |
|---|---|---|---|---|
| 1 | 46 | PDBIG · p. 5 | 4.2839 | Semantic + BM25 |
| 2 | 50 | PDBIG · p. 7 | 4.0616 | Semantic + BM25 |
| 3 | 41 | PDBIG · p. 1 | 2.7430 | Semantic |
| 4 | 47 | PDBIG · p. 6 | 2.5841 | Semantic |
| 5 | 43 | PDBIG · p. 4 | 2.5500 | BM25 |

## 7. Penalty

**Q:** What is the penalty for violating the Personal Data Protection Law?

>Based on the provided evidence, the Personal Data Protection Law specifies a penalty for one specific violation: **disclosing or publishing Sensitive Data with the intention of harming the Data Subject or achieving a personal benefit**. The penalty is **imprisonment for up to two years, a fine of up to three million Riyals, or both** [PDPL · Articles 34, 35 · p. 13].
> 
> The documents do not contain a comprehensive list of penalties for all possible violations of the Law.

| # | Chunk | Citation | Rerank score | Found by |
|---|---|---|---|---|
| 1 | 39 | PDPL · Articles 40, 41, 42 · p. 15 | 4.9285 | Semantic |
| 2 | 33 | PDPL · Articles 34, 35 · p. 13 | 2.5268 | BM25 |
| 3 | 43 | PDBIG · p. 4 | 0.0185 | Semantic |
| 4 | 21 | PDPL · Articles 19, 20, 21 · p. 9 | 0.0038 | Semantic |
| 5 | 45 | PDBIG · p. 5 | -0.2441 | Semantic |

## 8. Out of scope (AI)

**Q:** What is artificial intelligence?

>The provided documents do not contain enough information to answer the question about what artificial intelligence is. The evidence consists solely of excerpts from the Personal Data Protection Law (PDPL) covering topics such as data collection purposes, competent authority powers, penalties for violations, and complaint procedures, with no mention of artificial intelligence.

| # | Chunk | Citation | Rerank score | Found by |
|---|---|---|---|---|
| 1 | 12 | PDPL · Article 11 · p. 6 | -10.8779 | BM25 |
| 2 | 36 | PDPL · Article 37 · p. 14 | -11.0215 | Semantic |
| 3 | 33 | PDPL · Articles 34, 35 · p. 13 | -11.0449 | Semantic |
| 4 | 37 | PDPL · p. 14 | -11.0770 | Semantic |
| 5 | 32 | PDPL · Articles 32, 33 · p. 13 | -11.0828 | Semantic |

## Comparison

| # | Question | Candidates after merge | Top-5 found by both | Best chunk | Best score | Outcome |
|---|---|---|---|---|---|---|
| 1 | Personal data (Art. 1) | 15 | 2/5 | PDPL · Article 1 · p. 2 | 6.9894 | Correct |
| 2 | Processing without consent (Art. 6) | 13 | 4/5 | PDPL · Article 6 · p. 4 | 9.3053 | Correct |
| 3 | Sensitive data | 14 | 4/5 | PDPL · p. 10 | 1.4695 | Correct, definition truncated by chunk boundary |
| 4 | Notifying SDAIA | 13 | 5/5 | PDBIG · p. 5 | 8.4638 | Correct, both documents used |
| 5 | Breach handling stages | 14 | 5/5 | PDBIG · p. 6 | 7.5693 | Correct |
| 6 | Breach risks | 15 | 2/5 | PDBIG · p. 5 | 4.2839 | Correct |
| 7 | Penalty | 17 | 0/5 | PDPL · Articles 40, 41, 42 · p. 15 | 4.9285 | Correct, scope stated |
| 8 | Out of scope (AI) | 19 | 0/5 | PDPL · Article 11 · p. 6 | -10.8779 | Declined correctly |

**Reading the table**

- *Candidates after merge* is the number of unique chunks left after combining the two top-10 lists (20 minus the overlap). A smaller number means the two retrievers agreed more.
- *Top-5 found by both* shows how many of the final chunks were proposed by semantic search and BM25 together. Across all runs: 22 of 40 by both, 12 by semantic search only, 6 by BM25 only.
- *Best score* is the Cross-Encoder score of the top chunk. In-scope questions score between 4 and 9; the out-of-scope question scores about −11, which is what makes the refusal in test 8 reliable.
- Test 3 is the one weak answer: the definition of sensitive data is split across two chunks, so the model returned it incomplete rather than guessing the rest.
