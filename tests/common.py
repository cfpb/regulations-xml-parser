# Things common to many tests, such as a sample XML tree, so it can be imported

test_xml = """
        <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
          <fdsys>
            <date>2015-11-17</date>
            <title>REGULATION TESTING</title>
          </fdsys>
          <preamble>
            <cfr>
              <title>12</title>
              <section>1234</section>
            </cfr>
            <documentNumber>2015-12345</documentNumber>
            <effectiveDate>2015-11-17</effectiveDate>
            <federalRegisterURL>https://www.federalregister.gov/some/url/</federalRegisterURL>
          </preamble>
          <part label="1234">
            <content>

              <subpart>
                <content>
                  <section label="1234-1">
                    <subject/>
                    <paragraph label="1234-1-p1" marker="">
                      <content>I'm an unmarked paragraph</content>
                    </paragraph>
                    <paragraph label="1234-1-a" marker="a">
                      <content>I'm a marked paragraph</content>
                      <paragraph label="1234-1-a-p1" marker="">
                        <content>We are unmarked paragraphs</content>
                      </paragraph>
                      <paragraph label="1234-1-a-p2" marker="">
                        <content>We are unmarked paragraphs</content>
                      </paragraph>
                    </paragraph>
                  </section>
                </content>
              </subpart>

              <appendix appendixLetter="A" label="1234-A">
                <appendixTitle>Appendix A to Part 1234</appendixTitle>
                <appendixSection appendixSecNum="1" label="1234-A-p1">
                  <subject/>
                  <paragraph label="1234-A-p1-p1" marker="">
                    <content>This is some appendix content.</content>
                  </paragraph>
                </appendixSection>
              </appendix>

              <interpretations label="1234-Interp">
                <title>Supplement I to Part 1234&#8212;Official Interpretations</title>
                <interpSection label="1234-1-Interp" target="1234-1">
                  <title>Introduction</title>
                  <interpParagraph label="1234-1-A-Interp" target="1234-1-A">
                    <title type="keyterm">An initial keyterm</title>
                    <content>Some interpretation content here.</content>
                  </interpParagraph>
                  <interpParagraph label="1234-1-A-Interp-1">
                    <content>Interp paragraph without target.</content>
                  </interpParagraph>
                </interpSection>
              </interpretations>

            </content>
          </part>
          <analysis>
            <analysisSection target="1234-1" notice="2015-12345" date="2015-11-17">
              <title>Section 1234.1</title>
              <analysisParagraph>This paragraph is in the top-level section.</analysisParagraph>
              <analysisSection>
                <title>(a) Section of the Analysis</title>
                <analysisParagraph>I am a paragraph<footnote ref="1">Paragraphs contain text.</footnote> in an analysis<footnote ref="2">Analysis analyzes things.</footnote> section, love me!</analysisParagraph>
                <analysisParagraph>I am a paragraph with <em>italicized</em> text.</analysisParagraph>
              </analysisSection>
            </analysisSection>
            <analysisSection target="1234-1" notice="2014-12345" date="2014-11-17">
              <title>Section 1234.1</title>
              <analysisParagraph>This paragraph.</analysisParagraph>
            </analysisSection>
          </analysis>
        </regulation>
        """
