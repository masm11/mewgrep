import java.io.*;
import java.net.*;
import java.util.Set;
import java.util.HashSet;
import java.util.regex.Pattern;
import java.util.regex.Matcher;

import org.json.JSONObject;
import org.json.JSONArray;

import com.worksap.nlp.sudachi.*;

public class MewGrepTokenizer {
    
    private static String readAll(String filename)
	    throws IOException {
	BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(filename)));
	
	StringBuilder sb = new StringBuilder();
	while (true) {
	    String line = br.readLine();
	    if (line == null)
		break;
	    sb.append(line);
	}
	
	return sb.toString();
    }
    
    private static class TokenizerService implements Runnable {
	private Dictionary dict;
	private ServerSocket serverSocket;
	private Tokenizer tokenizer;
	private Pattern pat_emoji;
	private Pattern pat_symbol_only;
	private Set<String> ignoreType;
	private Tokenizer.SplitMode[] modes;
	public TokenizerService(Dictionary dict, ServerSocket serverSocket) {
	    this.dict = dict;
	    this.serverSocket = serverSocket;
	    tokenizer = dict.create();
	    pat_emoji = Pattern.compile("[\\x{0001f000}-\\x{0001f9ff}]");
	    pat_symbol_only = Pattern.compile("^[\\x00-/:-@\\[-`{-\\x7f]*$");
	    ignoreType = new HashSet<String>();
	    ignoreType.add("助詞");
	    ignoreType.add("補助記号");
	    modes = new Tokenizer.SplitMode[] {
		Tokenizer.SplitMode.A,
		Tokenizer.SplitMode.B,
		Tokenizer.SplitMode.C,
	    };
	}
	
	private String readAll(Socket sock)
		throws IOException {
	    InputStream is = sock.getInputStream();
	    ByteArrayOutputStream baos = new ByteArrayOutputStream();
	    byte[] buf = new byte[1024];
	    while (true) {
		int siz = is.read(buf);
		if (siz == -1)
		    break;
		baos.write(buf, 0, siz);
	    }
	    return new String(baos.toByteArray(), "UTF-8");
	}
	
	public void run() {
	    // System.out.println("run.");
	    while (true) {
		// System.out.println("iter.");
		try (Socket sock = serverSocket.accept()) {
		    // System.out.println("read.");
		    String json = readAll(sock);
		    
		    JSONObject obj = new JSONObject(json);
		    String reqModes = obj.getString("modes");
		    String reqText = obj.getString("text");
		    
		    Tokenizer.SplitMode[] selectedModes;
		    if (reqModes == "ABC") {
			selectedModes = new Tokenizer.SplitMode[] {
			    Tokenizer.SplitMode.A,
			    Tokenizer.SplitMode.B,
			    Tokenizer.SplitMode.C,
			};
		    } else {
			selectedModes = new Tokenizer.SplitMode[] {
			    Tokenizer.SplitMode.C,
			};
		    }
		    
		    Set<String> words = new HashSet<String>();
		    
		    Matcher mat = pat_emoji.matcher(reqText);
		    reqText = mat.replaceAll(" ");
		    
		    // System.out.println("tokenize.");
		    for (Tokenizer.SplitMode mode: selectedModes) {
			for (Morpheme m: tokenizer.tokenize(Tokenizer.SplitMode.A, reqText)) {
			    // System.out.println(m.partOfSpeech().get(0));
			    if (ignoreType.contains(m.partOfSpeech().get(0)))
				continue;
			    String word = m.normalizedForm();
			    if (pat_symbol_only.matcher(word).matches())
				continue;
			    words.add(word);
			}
		    }
		    
		    JSONArray arr = new JSONArray();
		    // System.out.println("make.");
		    for (String str: words)
			arr.put(str);
		    // System.out.println("send.");
		    sock.getOutputStream().write(arr.toString().getBytes("UTF-8"));
		} catch (IOException e) {
		    e.printStackTrace();
		} finally {
		}
	    }
	    // System.out.println("leave.");
	}
    }
    
    public static void main(String[] args)
	    throws Exception {
	String settings = readAll("./sudachi.json");
	Dictionary dict = new DictionaryFactory().create(settings);
	Tokenizer tokenizer = dict.create();
	
	ServerSocket socket = new ServerSocket(18080, 5, InetAddress.getLoopbackAddress());
	
	Thread[] threads = new Thread[5];
	for (int i = 0; i < 5; i++) {
	    TokenizerService svc = new TokenizerService(dict, socket);
	    threads[i] = new Thread(svc);
	    threads[i].start();
	}
	
	for (int i = 0; i < 5; i++)
	    threads[i].join();
    }
}
