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
    """
    new_parent = soup.new_tag("span")
    tokens = re.findall(r'\S+', s)  # Change back to \S+ to include punctuation
    
    for token in tokens:
        # Skip empty tokens
        if not token:
            continue
            
        # Find the first alphanumeric sequence to determine how much to bold
        alpha_match = re.search(r'(\w+)', token)
        
        if alpha_match:
            # Get the alphanumeric part and its position
            alpha = alpha_match.group(1)
            alpha_start = token.find(alpha)
            
            # Calculate bold count based on the alphanumeric part's length
            alpha_length = len(alpha)
            if alpha_length <= 3:
                bold_count = 1
            elif alpha_length == 4:
                bold_count = 2
            else:
                bold_count = max(1, int(alpha_length * 0.4))
                
            # Bold the appropriate part of the token
            prefix = token[:alpha_start]
            bold_part = token[alpha_start:alpha_start + bold_count]
            suffix = token[alpha_start + bold_count:]
            
            if prefix:
                new_parent.append(soup.new_string(prefix))
                
            b_tag = soup.new_tag("b")
            b_tag.append(soup.new_string(bold_part))
            new_parent.append(b_tag)
            
            new_parent.append(soup.new_string(suffix + " "))
        else:
            # This token has no alphanumeric part (e.g., punctuation only)
            new_parent.append(soup.new_string(token + " "))
            
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
