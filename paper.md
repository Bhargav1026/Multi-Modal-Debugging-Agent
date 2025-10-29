---
title: "Multi-Modal Debugging Agent: An Intelligent Tool for Debugging Across Modalities"
authors:
  - name: "Bhargava Sai Vardhan Gunapu"
    affiliation: "University of North Texas, USA"
  - name: "Vidya Vathi Gorji"
    affiliation: "Terralogic, India"
  - name: "Devi Pravallika Gunapu"
    affiliation: "Cotality, USA"
date: 2025-10-29
bibliography: paper.bib
---

# Summary

Debugging is a time-consuming and essential part of software development. Traditional tools depend mostly on text-based logs and breakpoints, which often fail to capture the complexity of modern multi-modal systems that integrate text, images, and other forms of data. The Multi-Modal Debugging Agent (MMDA) assists developers in diagnosing and resolving bugs by processing different types of input—code, logs, screenshots, and user interactions. By combining advances in natural language processing and computer vision, MMDA provides contextual debugging support that helps identify issues more quickly and efficiently.

# Statement of Need

Modern software frequently integrates multiple data modalities, making debugging more complex. Developers often struggle to link information across formats—such as connecting error logs with visual UI states or user actions. Existing tools rarely handle these heterogeneous data types in a unified way. MMDA fills this gap by offering a single framework that interprets and synthesizes multi-modal inputs. It is particularly useful for developers building applications with rich interfaces, embedded systems, and AI-driven features.

# Software Description

MMDA is implemented as a modular software agent that accepts different forms of input during a debugging session:

- Textual inputs: Source code snippets, stack traces, error logs, and developer queries  
- Visual inputs:  Screenshots, UI mockups, and video recordings of user interactions  
- Interactive inputs: User annotations and feedback

Its core includes:
- A **multi-modal encoder** that merges textual and visual information into a unified representation  
- A **reasoning engine** that uses rule-based logic and machine learning to identify likely bug causes  
- A **user interface** that presents insights, recommendations, and suggested fixes in a clear format  

MMDA also includes a Root Cause Analysis (RCA) pipeline for systematic diagnosis, a sandbox environment for safe testing of fixes, and an orchestration graph to manage communication between modules. These components together create an integrated debugging workflow. The system is compatible with common development environments and version control systems for easy integration.


# Illustrative Example

Take an example of a developer of a mobile application that is crashing intermittently when a particular button is pressed. When the developer is using MMDA, they add the corresponding code segment, a screen shot of the app when the failure occurred, and the log. MMDA works out these inputs, and identifies a mismatch between the state of the UI and the predicted behaviour of the source, and proposes that a null pointer exception could be caused by an uninitialised variable. It also suggests a patch to the code in order to set the variable and has links to documentation on the pertinent. This multi-modal method detects and fixes bugs much faster than the conventional log-only debugging.

# Quality Assurance

MMDA has been subjected to certain tests including:

- **Unit tests** of all core modules that are to verify that the multi-modal data processing is correct.
- **End-to-end verification/test** of end-to-end workflows with synthetic and real-world debugging.
- **User studies** of professional developers who said they had more efficient and satisfying debugging.
- Ongoing comparisons with the state-of-the-art debugging tools proved the superiority of MMDA that is able to process multi-modal data and deliver the actionable information.

The software is version controlled and has continuous integration pipelines to facilitate the continuity of reliability and performance.

# Impact and Reuse

MMDA can help developers save a lot of debugging and time as well as make software quality better by allowing developers to use multi-modal data appropriately. It promotes interdisciplinary relationships between fields as it combines natural language processing and computer vision knowledge to software engineering. The modular structure of MMDA and open APIs promote extension and customization to various areas of application. MMDA parts can also be reused by researchers and practitioners in similar tasks, including automated testing, user behavior analysis and software maintenance.

# Author Contributions

- **Bhargava Sai Vardhan Gunapu:** Lead architecture design, RCA pipeline, sandbox environment, orchestration graph, FastAPI backend, and documentation.  
- **Vidya Vathi Gorji:** VS Code extension development, frontend–backend integration, demo workflow design, and extensive testing.  
- **Devi Pravallika Gunapu:** Evaluation, quality assurance, reproducibility testing, and technical documentation preparation.

# Acknowledgements

The researchers thank the University of North Texas for supporting this study and the valuable feedback of the research developers. It is also important to note that the development of MMDA owes a lot to open-source communities whose tools and libraries made the creation of MMDA possible.

An archived version of this software is available at Zenodo (DOI: [10.5281/zenodo.17411418](https://doi.org/10.5281/zenodo.17411418)).

# References