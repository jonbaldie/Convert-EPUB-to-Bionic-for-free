import streamlit as st
import tempfile
import re
from tqdm import tqdm
from pathlib import Path
import subprocess

# Install beautifulsoup4 and ebooklib packages
subprocess.run(["pip", "install", "beautifulsoup4", "ebooklib"])

from bs4 import BeautifulSoup
import bs4
from ebooklib import epub

def _convert_file_path(path, original_name):
    path_obj = Path(path)
    new_name = f"Bionic_{original_name}"
    new_path = path_obj.with_name(new_name)
    return str(new_path)

def convert_to_bionic_str(soup: BeautifulSoup, s: str):
    """
    Convert text to bionic reading format based on word length:
    - Words ≤ 3 letters: first letter is bold
    - Words = 4 letters: first two letters are bold
    - Words > 4 letters: first 40% of letters are bold
    This version treats dash characters (and similar ones) as word boundaries.
    """
    new_parent = soup.new_tag("span")

    # First, split on whitespace to preserve spaces.
    chunks = re.split(r'(\s+)', s)

    for chunk in chunks:
        if not chunk:
            continue
        
        # If the chunk is whitespace, add it directly.
        if chunk.isspace():
            new_parent.append(soup.new_string(chunk))
            continue
        
        # For non-space chunks, further split on dash characters.
        # The regex will capture groups of dashes (or similar characters) as separate tokens.
        subchunks = re.split(r'([-–—]+)', chunk)
        
        for subchunk in subchunks:
            if not subchunk:
                continue
                
            # If the token is only made of dashes (or similar), leave it untouched.
            if re.fullmatch(r'[-–—]+', subchunk):
                new_parent.append(soup.new_string(subchunk))
            else:
                # Otherwise, process this token with the bionic transformation.
                # Count only alphanumeric characters for determining the bold count.
                alpha_count = sum(1 for c in subchunk if c.isalnum())
                
                if alpha_count == 0:
                    # If there are no alphanumerics, just add the token as is.
                    new_parent.append(soup.new_string(subchunk))
                else:
                    if alpha_count <= 3:
                        bold_count = 1
                    elif alpha_count == 4:
                        bold_count = 2
                    else:
                        bold_count = max(1, int(alpha_count * 0.4))
                    
                    bold_chars = 0
                    # Walk through the characters; when we've passed the bold_count for alphanumerics,
                    # split the token so that the first part will be bold.
                    for i, char in enumerate(subchunk):
                        if char.isalnum():
                            bold_chars += 1
                            if bold_chars > bold_count:
                                # Create the bold-tag for the part that should be bold.
                                b_tag = soup.new_tag("b")
                                b_tag.append(soup.new_string(subchunk[:i]))
                                new_parent.append(b_tag)
                                # Append the rest as plain text.
                                new_parent.append(soup.new_string(subchunk[i:]))
                                break
                    else:
                        # If the loop is not broken (all alphanumerics are within bold_count),
                        # then everything gets bolded.
                        b_tag = soup.new_tag("b")
                        b_tag.append(soup.new_string(subchunk))
                        new_parent.append(b_tag)
                    
    return new_parent

def convert_to_bionic(content: str):
    soup = BeautifulSoup(content, 'html.parser')
    for e in soup.descendants:
        if isinstance(e, bs4.element.Tag):
            if e.name == "p":
                children = list(e.children)
                for child in children:
                    if isinstance(child, bs4.element.NavigableString):
                        if len(child.text.strip()):
                            child.replace_with(convert_to_bionic_str(soup, child.text))
    return str(soup).encode()

def convert_book(book_path, original_name):
    source = epub.read_epub(book_path)
    total_items = len(list(source.items))
    progress_bar = st.progress(0)
    
    for i, item in enumerate(source.items):
        if item.media_type == "application/xhtml+xml":
            content = item.content.decode('utf-8')
            item.content = convert_to_bionic(content)
        progress_bar.progress((i + 1) / total_items)
    
    converted_path = _convert_file_path(book_path, original_name)
    epub.write_epub(converted_path, source)
    
    with open(converted_path, "rb") as f:
        converted_data = f.read()
    
    return converted_data, Path(converted_path).name

def main():
    st.title("Convert your EPUB to Bionic")
    book_path = st.file_uploader("Upload a book file", type=["epub"])

    if book_path is not None:
        original_name = book_path.name
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(book_path.read())
            tmp_file_path = tmp_file.name

        # Check if the uploaded book is different from the previous one
        if 'original_name' not in st.session_state or st.session_state.original_name != original_name:
            # Clear the session state if the book is different
            st.session_state.clear()

        # Perform the conversion only if the converted data is not already in the session state
        if 'converted_data' not in st.session_state:
            with st.spinner("Processing the file..."):
                st.session_state.converted_data, st.session_state.converted_name = convert_book(tmp_file_path, original_name)
            st.success("Conversion completed!")

        # Display the download button using the converted data from the session state
        converted_data = st.session_state.converted_data
        converted_name = st.session_state.converted_name
        st.download_button(
            label="Download Converted Book",
            data=converted_data,
            file_name=converted_name,
            mime="application/epub+zip"
        )

        # Store the original name of the uploaded book in the session state
        st.session_state.original_name = original_name

if __name__ == "__main__":
    main()
