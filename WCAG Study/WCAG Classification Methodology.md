We categorized the WCAG success criteria using the following approach. First, we defined the characteristics of issues that require static analysis and those that require dynamic analysis. Static analysis involves examining HTML, CSS, and JavaScript code, while dynamic analysis requires interactions with the application to gather useful information. Then, we reviewed all the success criteria in the WCAG and attempted to map each one to either static or dynamic analysis. The screenshot below illustrates how the success criterion SC 3.1.1 is categorized under static analysis, as its goal is to ensure the predominant language of a page is specified. As highlighted in the red box, this can be achieved by setting the language attribute on the HTML element. Since the language attribute is directly analyzed through HTML, it naturally falls within the static analysis category.

![img](https://lh7-rt.googleusercontent.com/docsz/AD_4nXe4HUPv_5Tfx1INfQqSLemKp7p1jHAWlOiY9jOG5WqJy-aLg02J243jdZhDx_wGTH3KvmrdFxotKxahg6KJ1LM5w24ZWAD3KNxz8-wViGtes3tgCY91RqDk1nEkFgYxCsWkqbRVLA?key=mx2ET2eS5ycclHd4oSNJdiI6)



By contrast, the screenshot of SC 2.5.1 below indicates it needs dynamic analysis, as illustrated by the keyword “Let users operate” in its Goal.

![img](https://lh7-rt.googleusercontent.com/docsz/AD_4nXfD7VLor9BEpiHTmrccJ02Q2e217vONUsvo9yzoNj0p4yHJ71Gj33hiZZMH3HBaShng9tBRHHdM-DDAvYlsepfT8y2CIEmxTHm4KTda0DztcDNiFhOIN7z2769t7decMLWFZWxnTA?key=mx2ET2eS5ycclHd4oSNJdiI6)



During this process, we found that certain success criteria are not testable, as specifically noted by the WCAG—for example, success criterion 3.1.5 Reading Level. This led us to establish a third category for untestable criteria. 

![img](https://lh7-rt.googleusercontent.com/docsz/AD_4nXd8vT6bGpeadpL-YLZfSwkRl0qu-Ty_eKeR6-w5E51LIfr2lAumSwxVxMGQmhYc2JFErzYhy272FZBsRMri_lR5GFGAHDq1N_35scA5hq45JhWRd_W9LJvolW6cOoxYvPGyC6j7?key=mx2ET2eS5ycclHd4oSNJdiI6)



To ensure the reliability of our classification of WCAG success criteria into static and dynamic analysis categories, we performed cross-validation using the documentation of two widely used accessibility evaluation tools: WAVE and IBM Equal Access. We observed that success criteria documented with specific violations in these tools typically fall under **static analysis**, as these violations can be detected without requiring user interaction. Conversely, success criteria that are mentioned without specified violations often require **dynamic analysis**, involving user interactions or behaviors.

For example, in the IBM Equal Access documentation, **SC 3.1.1 Language of Page** has several documented violations—such as missing lang attributes in the HTML—that can be identified through static analysis. ![img](https://lh7-rt.googleusercontent.com/docsz/AD_4nXcZxZfHAK7yvTzt39fbh51V631uBluqlkRdYy5RZyQs_et1avMDaozqrM3BJ2Cq7g0BC-2tepUjs6wATsCpz8WtpJR0NU0HBKXi55bF9tA_q24IWky64-8WrZhgqCtE6RHWMSKklw?key=mx2ET2eS5ycclHd4oSNJdiI6)



In contrast, **SC 2.5.1 Pointer Gestures** and **SC 2.5.2 Pointer Cancellation** lack specific documented violations and involve user interactions like multi-point gestures or touch events, indicating the need for dynamic analysis. By cross-referencing the presence or absence of documented violations and considering the nature of each success criterion, we validated our classification into static and dynamic categories.

![img](https://lh7-rt.googleusercontent.com/docsz/AD_4nXcpF2f5ax5KzZJ8gDcSUPY-5YP7Mk-rAGxL-spcmvFDaDvGFlvzHSsjyLya0msDfGTLIOdPMcTP_UeAbQknRBIFAJbadT6tAHrLwr2kddZ09BhVwffiJmkyGDm2anxZp2Lkf5DHZg?key=mx2ET2eS5ycclHd4oSNJdiI6)